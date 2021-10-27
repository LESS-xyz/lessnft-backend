import logging
from os import PRIO_PROCESS
import sys
import threading
import time
import traceback

from dds.accounts.models import AdvUser
from dds.activity.models import BidsHistory, TokenHistory
from dds.store.models import *
from django.db.models import F
from web3 import Web3

from utils import get_last_block, save_last_block
from typing import Optional


def never_fall(func):
    def wrapper(*args, **kwargs):
        while True:
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(
                    "\n".join(traceback.format_exception(*sys.exc_info())), flush=True
                )
                time.sleep(60)

    return wrapper


def print_log(network, text):
    print(f'{network}: {text}')


class ScannerAbsolute(threading.Thread):
    """
    Abstract class for event scanner

    You should change events and block_filename in child class
    Also you need change method save_new_presale and write logic for your scanner

    network - muncify object
    event_names = list event names of contract
    type - type of your contract. made for application with plural contract
    """

    def __init__(
        self,
        network: object,
        type_contract: str,
        handler: object
        ) -> None:
        super().__init__()

        self.network = network
        self.type_contract = type_contract
        self.handler = handler
        self.block_filename = f'{network.name}-{handler.__name__}-{type_contract}'
        print_log(self.network, 'scanner init')

    def run(self):
        self.start_polling()

    @never_fall
    def start_polling(self) -> None:
        print_log(self.network, 'start polling')
        while True:
            last_block_checked = get_last_block(
                    self.block_filename,
                    self.network.name
                    )
            last_block_network = self.network.get_last_confirmed_block()
            if last_block_checked - last_block_network < 2:
                print_log(self.network, 'time for sleep!')
                time.sleep(self.network.check_timeout)
                continue

            # self.save_new_presale(last_block_checked, last_block_network)
            self.handler(
                last_block_checked,
                last_block_network,
                self.network,
                self.type_contract
                ).start()

            save_last_block(
                last_block_network,
                self.block_filename
            )

            time.sleep(self.network.check_timeout)


class HandlerDeploy:
    def __init__(
        self,
        last_block_checked,
        last_block_network,
        network,
        type_contract
        ) -> None:
        self.event = {
            'ERC721': network.get_erc721fabric_contract()[1].events.ERC721Made,
            'ERC1155': network.get_erc1155fabric_contract()[1].events.ERC1155Made
            }[type_contract]
        self.last_block_checked = last_block_checked
        self.last_block_network = last_block_network 

    def start(self,) -> None:
        print('start handler!')
        event_filter = self.event.createFilter(
            fromBlock=self.last_block_checked, 
            toBlock=self.last_block_network
        )
        event_list = event_filter.get_all_entries()
        map(self.save_event, event_list)

    def save_event(self, event_data):
        print('in save event')
        deploy_hash = event_data['transactionHash'].hex()
        deploy_block = event_data['blockNumber']
        address = Web3.toChecksumAddress(
            event_data['args']['newToken'])

        collection = Collection.objects.filter(deploy_hash=deploy_hash)
        if not collection.exists():
            return

        collection.update(
            status=Status.COMMITTED,
            deploy_block=deploy_block,
            address=address,
        )


class HandlerMintTransferBurn:
    '''
    необходимо доработать хэндлер
    нет коллекций
    нет нетвокра
    '''
    def __init__(
        self,
        last_block_checked,
        last_block_network,
        network,
        type_contract
        ) -> None:
        self.event = {
            'ERC721': network.get_erc721main_contract()[1].events.Transfer,
            'ERC1155': network.get_erc1155main_contract()[1].events.TransferSingle
            }[type_contract]
        self.last_block_checked = last_block_checked
        self.last_block_network = last_block_network 
        self.empty_address = '0x0000000000000000000000000000000000000000'

    def start(self,) -> None:
        print('start handler!')
        event_filter = self.event.createFilter(
            fromBlock=self.last_block_checked, 
            toBlock=self.last_block_network
        )
        event_list = event_filter.get_all_entries()
        map(self.save_event, event_list)

    def save_event(self, event_data):
        tx_hash = event_data['transactionHash'].hex()
        event_args = event_data['args']

        key_token_id = 'id' if 'id' in event_args.keys() else 'token_id'
        token_id = event_args.get(key_token_id)

        new_owner_address = event_args.get('to').lower()
        new_owner = self.get_owner(new_owner_address)
        old_owner_address = event_args.get('from').lower()
        old_owner = self.get_owner(old_owner_address)

        try:
            token = self.get_buyable_token(
                event_args,
                token_id,
                collection,
                smart_contract
                )
        except Token.DoesNotExist:
            return

        if old_owner_address == self.empty_address:
            self.mint_event(token, token_id, tx_hash, new_owner)
        elif new_owner_address == self.empty_address:
            self.burn_event(token, tx_hash, event_args, old_owner)
        else:
            self.transfer_event(
                token,
                tx_hash,
                token_id,
                new_owner,
                old_owner,
                event_args
                )
        

    def get_owner(self, new_owner_address: str) -> Optional[AdvUser]:
        try:
            new_owner = AdvUser.objects.get(username=new_owner_address)
        except AdvUser.DoesNotExist:
            new_owner = None
        return new_owner

    def get_buyable_token(
        self,
        event_args: dict,
        token_id: int,
        collection: Collection,
        smart_contract
        ) -> Token:
        if event_args['to'] == self.empty_address:
            token = Token.objects.filter(internal_id__isnull=False).get(
                internal_id=token_id,
                collection__address=collection.address,
            )
        else:
            ipfs = get_ipfs(token_id, smart_contract)
            token = Token.objects.get(
                ipfs=ipfs, 
                collection=collection,
            )
        return token

    def mint_event(
        self,
        token: Token,
        token_id: int,
        tx_hash: str,
        new_owner: AdvUser
        ) -> None:
        token.update(
            status=Status.COMMITTED,
            internal_id=token_id,
            tx_hash=tx_hash,
        )
        TokenHistory.objects.get_or_create(
            token=token,
            tx_hash=tx_hash,
            method='Mint',
            new_owner=new_owner,
            old_owner=None,
            price=None,
        )

    def burn_event(
        self,
        token: Token,
        tx_hash: str,
        event_args: dict,
        old_owner: AdvUser
        ) -> None:
        TokenHistory.objects.get_or_create(
            token=token,
            tx_hash=tx_hash,
            method='Burn',
            new_owner=None,
            old_owner=None,
            price=None,
            amount=event_args.get('value'),
        )
        if token.standart == 'ERC721':
            token.update(status=Status.BURNED)
        elif token.standart == 'ERC1155':
            if token.total_supply:
                token.update(total_supply=F('total_supply')-event_args['value'])
            token.save()
            # self.change_quantity_ownership(old_owner, token, event_args)

    def change_quantity_old_ownership(
        self,
        old_owner: AdvUser,
        token: Token,
        event_args:dict
        ) -> None:
        ownership = Ownership.objects.get(owner=old_owner, token=token)
        ownership.quantity = ownership.quantity - event_args['value']
        ownership.save()
        if ownership.quantity <= 0:
            ownership.delete()
        if token.total_supply == 0:
            token.status=Status.BURNED
            token.save()

    def transfer_event(
        self,
        token: Token,
        tx_hash: str,
        token_id: int,
        new_owner: AdvUser,
        old_owner: AdvUser,
        event_args:dict
        ) -> None:
        token.update(
            tx_hash=tx_hash,
            internal_id=token_id,
        )
        if token.standart == 'ERC721':
            token.update(owner=new_owner, selling=False, currency_price=None)

        try: 
            token_history = TokenHistory.objects.get(tx_hash=tx_hash)
            if token_history.method == 'Buy':
                return
        except TokenHistory.DoesNotExist:
            TokenHistory.objects.get_or_create(
                token=token,
                tx_hash=tx_hash,
                method='Transfer',
                new_owner=new_owner,
                old_owner=old_owner,
                price=None,
                amount=event_args.get('value'),
            )

        # self.change_quantity_old_ownership(old_owner, token, event_args)
        # self.change_quantity_new_ownership()

    # def change_quantity_new_ownership(self) -> None:
        # pass
    def change_quantity_if_ERC1155(self, token, old_owner, event_args):
        if token.standart == 'ERC721':
            return
        self.change_quantity_old_ownership(old_owner, token, event_args) 
        price = old_owner.currency_price
        self.change_quantity_new_ownership(new_owner, token, event_args, price)
        
    def change_quantity_new_ownership(
        self,
        new_owner: AdvUser,
        token: Token,
        event_args: dict,
        price
        ) -> None:
        try:
            ownership = Ownership.objects.get(owner=new_owner, token=token)
            ownership.quantity = ownership.quantity + event_args.get('value')
            ownership.currency_price = price
            ownership.save()
        except Ownership.DoesNotExist:
            Ownership.objects.create(
                owner=new_owner,
                token=token,
                quantity=event_args.get('value'),
                currency_price=price
            ).save()
            token.owner.add(new_owner).save()

class HandlerBuy:
    def __init__(
        self,
        last_block_checked,
        last_block_network,
        network,
        token_standart
        ) -> None:
        self.event = {
            'ERC721': network.get_exchange_contract()[1].events.ExchangeMadeErc721,
            'ERC1155': network.get_exchange_contract()[1].events.ExchangeMadeErc1155
            }[token_standart]
        self.last_block_checked = last_block_checked
        self.last_block_network = last_block_network 

    def start(self,) -> None:
        print('start handler!')
        event_filter = self.event.createFilter(
            fromBlock=self.last_block_checked, 
            toBlock=self.last_block_network
        )
        event_list = event_filter.get_all_entries()
        map(self.save_event, event_list)

    def save_event(self, event_data):
        event_args = event_data['args']
        sell_token = event_args['sellTokenAddress']
        token_id = event_args['sellId']
        tx_hash = event_data['transactionHash'].hex()
        new_owner = AdvUser.objects.get(username=event_args['buyer'].lower())
        old_owner = AdvUser.objects.get(username=event_args['seller'].lower())
        
        try:
            token = Token.objects.get(
                collection_address=sell_token,
                internal_id=token_id
            )
        except Token.DoesNotExist:
            return

        if token.standart == 'ERC721':
            self.buy_erc721(new_owner, token)
        elif token.standart == 'ERC1155':
            self.buy_1155()
        self.refresh_token_history(
            event_args,
            token,
            tx_hash,
            new_owner,
            old_owner
            )

    def buy_erc721(self, new_owner: AdvUser, token: Token):
        token.update(owner=new_owner, selling=False, currency_price=None)
        Bid.objects.filter(token=token).delete()

    def buy_erc1155(self, old_owner, token, event_args, new_owner, tx_hash):
            owner = Ownership.objects.filter(
                owner=new_owner,
                token=token[0]
            )
            logging.info(f'owner is {owner}')

            token_history_exist = TokenHistory.objects.filter(tx_hash=tx_hash, method='Transfer').exists()
            logging.info(f'token history {token_history_exist}')
            if owner.exists() and not token_history_exist:
                owner.update(quantity=F('quantity')+event_args['sellAmount'])
            elif not owner.exists():
                logging.info('ownership 404!')
                owner = Ownership.objects.create(
                    owner=new_owner,
                    token=token[0],
                    quantity=event_args['sellAmount'],
                )
                logging.info(f'create owner: {owner}')
                logging.info('who is owner? It is {owner.owner}')
                token[0].owners.add(new_owner)

            if not token_history_exist:
                owner = Ownership.objects.get(
                    owner=old_owner,
                    token=token[0]
                )
                owner.quantity = owner.quantity - event_args['sellAmount']
                if owner.quantity:
                    owner.save()
                if not owner.quantity:
                    owner.delete()

    def refresh_token_history(self, event_args, token, tx_hash, new_owner, old_owner):
        decimal_price = event_args["buyAmount"]
        decimals = token.currency.get_decimals
        price = Decimal(decimal_price / decimals) 

        token_history = TokenHistory.objects.filter(tx_hash=tx_hash)
        logging.info(f"token history: {token_history}")
        if token_history.exists():
            token_history.update(
                method="Buy",
                price=price,
                amount=event_args['sellAmount'],
            )
        else:
            TokenHistory.objects.get_or_create(
                token=token,
                tx_hash=tx_hash,
                new_owner=new_owner,
                old_owner=old_owner,
                method="Buy",
                price=price,
                amount=event_args['sellAmount'],
            )

class HandlerAprooveBet:
    def __init__(
        self,
        last_block_checked,
        last_block_network,
        network,
        token_standart
        ) -> None:
        self.event = {
            'ERC721': network.get_exchange_contract()[1].events.ExchangeMadeErc721,
            'ERC1155': network.get_exchange_contract()[1].events.ExchangeMadeErc1155
            }[token_standart]
        self.last_block_checked = last_block_checked
        self.last_block_network = last_block_network 

    def start(self,) -> None:
        print('start handler!')
        event_filter = self.event.createFilter(
            fromBlock=self.last_block_checked, 
            toBlock=self.last_block_network
        )
        event_list = event_filter.get_all_entries()
        map(self.save_event, event_list)

    def save_event(self, event_data):
        event_args = event_data['args']
        user = event_args['src'].lower()
        exchange = event_args['guy']

        bet = Bid.objects.filter(user__username=user)
        if not bet.exists():
            return

        wad = int(event_args['wad'])

        for item in bet:
            if wad > item.quantity * item.amount:
                item.state=Status.COMMITTED
                item.save()
                BidsHistory.objects.create(
                    token=item.token,
                    user=item.user,
                    price=item.amount,
                    date=item.created_at
                )
                logging.info('bet update! \n _______________')
            else:
                logging.info('no money!')
                return
