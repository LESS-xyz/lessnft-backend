import logging
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
        pass

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


'''
class ScannerBuy(ScannerAbstract):
    """
    class for catch buy events
    """

    def __init__(
        self, network: object, event_names: dict,
        contract_type: str, contract_address: str = None
        ) -> None:
        super().__init__(network, event_names, contract_type, contract_address)

        self.connection_type = {
            "exchange": self.network.get_exchange_contract()
        }
        self.block_filename = "_".join([self.network.name, "exchange"])

    def save_new_presale(
        self, last_block_checked: int, last_block_network: int
        ) -> None:
        for event in self.events:
            event_filter = event.createFilter(
                fromBlock=last_block_checked, toBlock=last_block_network
            )
            event_list = event_filter.get_all_entries()
            if not event_list:
                continue

            for event_data in event_list:
                logging.info("event_data:", event_data)
                new_owner, tx_hash, old_owner, token = self.get_event_params(event_data)
                logging.info("new owner:", new_owner)
                if not token.exists():
                    continue

                logging.info("tokens:", token)
                logging.info("token standart:", token[0].standart)
                if token[0].standart == "ERC721":
                    price, currency = self.buy_721(token, new_owner)
                elif token[0].standart == "ERC1155":
                    price, currency = self.buy_1155(
                        token,
                        old_owner,
                        new_owner,
                        tx_hash,
                        event_data["args"]["sellAmount"],
                    )

                logging.info(f"{token} update!")
                self.create_buy_token_history(
                    tx_hash, price, currency, token, new_owner, old_owner
                )

    def buy_721(self, token: Token, new_owner: AdvUser) -> tuple:
        price = token[0].currency_price
        currency = token[0].currency
        token.update(owner=new_owner, selling=False, currency_price=None)
        Bid.objects.filter(token=token[0]).delete()
        logging.info("all bids deleted!")

        return price, currency

    def buy_1155(
        self,
        token: Token,
        old_owner: AdvUser,
        new_owner: AdvUser,
        tx_hash: str,
        sell_amount: int,
        ) -> tuple:
        old_ownership = token[0].ownership_set.filter(owner=old_owner).first()
        price = old_ownership.currency_price
        currency = old_ownership.currency
        owner = Ownership.objects.filter(owner=new_owner, token=token[0])

        token_history_exist = TokenHistory.objects.filter(
            tx_hash=tx_hash, method="Transfer"
        ).exists()
        if owner.exists() and not token_history_exist:
            owner.update(quantity=F("quantity") + sell_amount)
        elif not owner.exists():
            logging.info("ownership 404!")
            owner = Ownership.objects.create(
                owner=new_owner,
                token=token[0],
                quantity=sell_amount,
            )
            logging.info("create owner:", owner)
            logging.info("who is owner? It is", owner.owner)
            token[0].owners.add(new_owner)

        if not token_history_exist:
            owner = Ownership.objects.get(owner=old_owner, token=token[0])
            owner.quantity = owner.quantity - sell_amount
            if owner.quantity:
                owner.save()
            if not owner.quantity:
                owner.delete()

        bet = Bid.objects.filter(token=token[0]).order_by("-amount")
        logging.info("bet:", bet)
        if bet.exists():
            if sell_amount == bet.first().quantity:
                logging.info("bet:", bet.first())
                bet.delete()
            else:
                quantity = bet.first().quantity - sell_amount
                Bid.objects.filter(id=bet.first().id).update(quantity=quantity)
            logging.info("bet upgraded")

        return price, currency

    def get_event_params(self, event_data: dict) -> tuple:
        new_owner = AdvUser.objects.get(username=event_data["args"]["buyer"].lower())
        tx_hash = event_data["transactionHash"].hex()
        old_owner = AdvUser.objects.get(username=event_data["args"]["seller"].lower())

        sell_token = event_data["args"]["sellTokenAddress"]
        token_id = event_data["args"]["sellId"]
        token = Token.objects.filter(
            collection__address=sell_token,
            internal_id=token_id,
        )

        return new_owner, tx_hash, old_owner, token

    def create_buy_token_history(
        self,
        tx_hash: str,
        price: int,
        currency,
        token: Token,
        new_owner: AdvUser,
        old_owner: AdvUser,
        ) -> None:
        token_history = TokenHistory.objects.filter(tx_hash=tx_hash)
        history_params = {
            "method": "Buy",
            "price": price,
            "currency": currency,
        }
        if token_history.exists():
            token_history.update(**history_params)
        else:
            TokenHistory.objects.get_or_create(
                token=token[0],
                tx_hash=tx_hash,
                new_owner=new_owner,
                old_owner=old_owner,
                **history_params,
            )


class AprooveBetScanner(ScannerAbstract):
    def __init__(
        self, network: object, event_names: dict, contract_type: str
        ) -> None:
        super().__init__(network, event_names, contract_type)

        self.connection_type = {
            "exchange": self.network.get_exchange_contract()
        }
        self.block_filename = "_".join([self.network.name, "aproove"])

    def save_new_presale(
        self, last_block_checked: int, last_block_network: int
        ) -> None:
        for event in self.events:
            event_filter = event.createFilter(
                fromBlock=last_block_checked, toBlock=last_block_network
            )
            event_list = event_filter.get_all_entries()
            if not event_list:
                continue
            
            for event_data in event_list:
                user = event_data["args"]["src"].lower()
                exchange = event_data["args"]["guy"]
                logging.info(f"exchange: {exchange} \n user: {user}")

                bet = Bid.objects.filter(user__username=user)
                logging.info(f"bet: {bet}")

                if (exchange != EXCHANGE_ADDRESS) or (not bet.exists()):
                    logging.info("not our exchage or not bet!")
                    continue

                wad = event_data["args"]["wad"]
                logging.info(f"wad: {wad}")

                self.create_bid_if_valid(bet, wad)

    def create_bid(self, item):
        item.state = Status.COMMITTED
        item.save()
        BidsHistory.objects.create(
            token=item.token, user=item.user, price=item.amount, date=item.created_at
        )
        logging.info("bet update! \n _______________")

    def create_bid_if_valid(self, bet, wad) -> None:
        for item in bet:
            bid_is_valid = wad > item.quantity * item.amount
            if bid_is_valid:
                self.create_bid(item)
'''
