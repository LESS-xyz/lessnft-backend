import logging
import sys
import threading
import time
import traceback

from dds_backend_2.dds.accounts.models import AdvUser
from dds_backend_2.dds.activity.models import BidsHistory, TokenHistory
from dds_backend_2.dds.store.models import *
from django.db.models import F
from settings import HOLDERS_CHECK_TIMEOUT
from web3 import Web3

from .utils import get_last_block, save_last_block


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


class ScannerAbstract(threading.Thread):
    """
    Abstract class for event scanner

    You should change events and block_filename in child class
    Also you need change method save_new_presale and write logic for your scanner

    network - muncify object
    event_names = list event names of contract
    type - type of your contract. made for application with plural contract
    """

    def __init__(
        self, network: object, event_names: list,
        type_contract: str, contract_address: str = None
        ) -> None:
        super().__init__()

        self.network = network
        self.events = [map(self.get_event, event_names)]
        self.type_contract = type_contract
        self.contract_address = contract_address
        self.connection_type = {}
        self.block_filename = "abstract_file"

    @never_fall
    def start_polling(self) -> None:
        while True:
            last_block_checked = get_last_block(self.block_filename)
            last_block_network = (
                self.network.w3.eth.block_number - \
                    self.network.confirmation_blocks
            )
            if last_block_checked <= last_block_network:
                time.sleep(self.network.check_timeout)
                continue

            self.save_new_presale(last_block_checked, last_block_network)

            save_last_block(last_block_network, self.block_filename)

            time.sleep(self.network.check_timeout)

    def save_new_presale(
        self, last_block_checked: int, last_block_network: int
        ) -> None:
        pass

    def get_event(self, event_name):
        if self.contract_address:
            contract_connection = self.network.get_token_contract(
                self.contract_address
            )[1]
        else:
            contract_connection = self.connection_type[self.type_contract]
        event = getattr(contract_connection.events, event_name)()
        return event


class ScannerDeploy(ScannerAbstract):
    """
    class for scan contract and catch event deploy
    """

    def __init__(
        self, network: object, event_names: dict, type_contract: str
        ) -> None:
        super().__init__(network, event_names, type_contract)

        self.connection_type = {
            "721": self.network.get_erc721fabric_contract(),
            "1155": self.network.get_erc1155fabric_contract()
        }
        self.block_filename = "_".join([self.network.name, "deploy"])

    def save_new_presale(
        self, last_block_checked: int, last_block_network: int
        ) -> None:
        for event in self.events:
            event_filter = event.createFilter(
                fromBlock=last_block_checked, toBlock=last_block_network
            )
            event_list = event_filter.get_all_entries()

            for event_data in event_list:
                deploy_hash = event_data["transactionHash"].hex()
                deploy_block = event_data["blockNumber"]
                address = Web3.toChecksumAddress(event_data["args"]["newToken"])

                collection = Collection.objects.filter(deploy_hash=deploy_hash)
                if not collection.exists():
                    continue

                collection.update(
                    status=Status.COMMITTED,
                    deploy_block=deploy_block,
                    address=address,
                )


class ScannerMintTransfer(ScannerAbstract):
    """
    class for check mint and transfer events
    """

    def __init__(
        self, network: object, event_names: dict,
        type_contract: str, contract_address: str = None
        ) -> None:
        super().__init__(network, event_names, type_contract, contract_address)

        self.connection_type = {
            "721": self.network.get_erc721main_contract(),
            "1155": self.network.get_erc1155main_contract()
        }
        self.block_frlename = "_".join([self.network.name, "mint_transfer"])

    def save_new_presale(
        self, last_block_checked: int, last_block_network: int
        ) -> None:
        collection = Collection.objects.get(address="")
        empty_address = "0x0000000000000000000000000000000000000000"

        for event in self.events:
            event_filter = event.createFilter(
                fromBlock=last_block_checked, toBlock=last_block_network
            )
            event_list = event_filter.get_all_entries()
            if not event_list:
                continue

            for event_data in event_list:
                tx_hash, token_id, new_owner, ipfs, token = self.get_event_params(
                    event_data, collection
                )
                if not token.exists() or not ipfs:
                    logging.warning("token 404!")
                    continue
                logging.info(f"get token {token[0].name}")

                # if from equal empty_address this is mint event
                if event_data["args"]["from"] == empty_address:
                    logging.info("Mint!")
                    self.mint(token, token_id, tx_hash, new_owner)

                # if from not equal empty_address tis is transfer event
                else:
                    old_owner_address = event_data["args"]["from"].lower()
                    old_owner = AdvUser.objects.get(username=old_owner_address)

                    if event_data["args"]["to"] == empty_address:
                        logging.info("Burn!")
                        self.burn(token, tx_hash, event_data["args"]["value"])

                    else:
                        logging.info("Transfer!")
                        transfer = self.transfer(
                            token, tx_hash, token_id, new_owner, old_owner
                        )
                        if not transfer:
                            continue

                    if token[0].standart == "ERC1155":
                        ownership = self.change_ownership_1155(
                            old_owner, token, event_data["args"]["value"],
                            new_owner
                        )
                        if not ownership:
                            continue

    def mint(
        self, token: Token, token_id: int, tx_hash: str, new_owner: AdvUser
        ) -> None:
        token.update(
            status=Status.COMMITTED,
            internal_id=token_id,
            tx_hash=tx_hash,
        )
        TokenHistory.objects.get_or_create(
            token=token[0],
            tx_hash=tx_hash,
            method="Mint",
            new_owner=new_owner[0],
            old_owner=None,
            price=None,
        )

    def burn(self, token: Token, tx_hash: str, value: int) -> None:
        TokenHistory.objects.get_or_create(
            token=token[0],
            tx_hash=tx_hash,
            method="Burn",
            new_owner=None,
            old_owner=None,
            price=None,
        )
        if token.first().standart == "ERC721":
            token.update(status=Status.BURNED)
        elif token.first().standart == "ERC1155":
            if token.first().total_supply:
                token.update(total_supply=F("total_supply") - value)
            # token[0].total_supply -= event['args']['value']
            token[0].save()
            if token[0].total_supply == 0:
                token.update(status=Status.BURNED)

    def transfer(
        self,
        token: Token,
        tx_hash: str,
        token_id: int,
        new_owner: AdvUser,
        old_owner: AdvUser,
        ) -> bool:
        token.update(
            owner=new_owner[0],
            tx_hash=tx_hash,
            internal_id=token_id,
        )

        token_history = TokenHistory.objects.filter(tx_hash=tx_hash)
        if token_history.exists():
            if token_history.first().method == "Buy":
                return False
        else:
            TokenHistory.objects.get_or_create(
                token=token.first(),
                tx_hash=tx_hash,
                method="Transfer",
                new_owner=new_owner[0],
                old_owner=old_owner,
                price=None,
            )
            return True

    def change_ownership_1155(
        self, old_owner: AdvUser, token: Token, value: int, new_owner: AdvUser
        ) -> bool:
        owner = Ownership.objects.filter(
            owner=old_owner,
            token=token.first(),
        )

        if not owner.exists():
            logging.info("old_owner is not exist!")
        else:
            if owner.first().quantity:
                owner.update(quantity=F("quantity") - value)
            else:
                owner.delete()

        owner = Ownership.objects.filter(owner=new_owner[0], token=token.first())
        if owner.exists():
            owner.update(quantity=F("quantity") + value)
        else:
            if not new_owner[0]:
                return False
            logging.info("ownership for new owner is not exist!")
            logging.info("new_owner:", new_owner)
            owner = Ownership.objects.create(
                owner=new_owner[0], token=token.first(), quantity=value
            )
            token.first().owners.add(owner)

        owner.save()
        return True

    def get_event_params(self, event_data: dict, collection) -> tuple:
        tx_hash = event_data["transactionHash"].hex()
        token_id = event_data["args"].get("tokenId")
        if not token_id:
            token_id = event_data["args"].get("id")

        new_owner_address = event_data["args"].get("to").lower()
        new_owner = AdvUser.objects.filter(username=new_owner_address)
        if not new_owner.exists():
            new_owner = [None]
        ipfs = get_ipfs(token_id, collection.address)
        try:
            ipfs = ipfs[6:]
        except:
            ipfs = None
        token = Token.objects.filter(
            ipfs=ipfs,
            collection=collection,
        )

        return tx_hash, token_id, new_owner, ipfs, token


class ScannerBuy(ScannerAbstract):
    """
    class for catch buy events
    """

    def __init__(
        self, network: object, event_names: dict,
        type_contract: str, contract_address: str = None
        ) -> None:
        super().__init__(network, event_names, type_contract, contract_address)

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
        self, network: object, event_names: dict, type_contract: str
        ) -> None:
        super().__init__(network, event_names, type_contract)

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
