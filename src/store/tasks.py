import logging
from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone
from tronapi import HttpProvider, Tron

from celery import shared_task
from src.celery import app
from src.networks.models import Network, Types
from src.settings import config
from src.store.models import Bid, Status, Tags, Token, TransactionTracker
from src.store.services.auction import check_auction_tx, end_auction
from src.store.services.collection_import import OpenSeaImport

logger = logging.getLogger("celery")


@shared_task(name="remove_pending_tokens")
def remove_pending_tokens():
    expiration_date = datetime.today() - timedelta(days=1)
    tokens = Token.objects.filter(
        status__in=(Status.PENDING, Status.FAILED),
        updated_at__lte=expiration_date,
    )
    logger.info(f"Pending {len(tokens)} tokens")
    tokens.delete()


@shared_task(name="remove_token_tag_new")
def remove_token_tag_new():
    tag = Tags.objects.filter(name="New").first()
    if tag is None:
        return
    tokens = Token.objects.filter(
        updated_at__lte=datetime.today()
        - timedelta(hours=config.CLEAR_TOKEN_TAG_NEW_TIME),
    )
    for token in tokens:
        token.tags.remove(tag)


@shared_task(name="end_auction_checker")
def end_auction_checker():
    tokens = Token.objects.committed().filter(
        end_auction__lte=datetime.today(),
    )
    for token in tokens:
        incorrect_bid_checker()
        if token.bid_set.count():
            tx_hash, network = end_auction(token)
            check_auction_tx(tx_hash, network)
        token.start_auction = None
        token.end_auction = None
        token.selling = False
        token.currency_minimal_bid = None
        token.save()


@shared_task(name="incorrect_bid_checker")
def incorrect_bid_checker():
    bids = Bid.objects.committed()
    for bid in bids:
        network = bid.token.currency.network
        user_balance = network.contract_call(
            method_type="read",
            contract_type="token",
            address=bid.token.currency.address,
            function_name="balanceOf",
            input_params=(bid.user.username,),
            input_type=("address",),
            output_types=("uint256",),
        )

        allowance = network.contract_call(
            method_type="read",
            contract_type="token",
            address=bid.token.currency.address,
            function_name="allowance",
            input_params=(
                bid.user.username,
                network.exchange_address,
            ),
            input_type=("address", "address"),
            output_types=("uint256",),
        )

        if (
            user_balance < bid.amount * bid.quantity
            or allowance < bid.amount * bid.quantity
        ):
            bid.state = Status.EXPIRED
            bid.save()


def check_ethereum_transactions(tx) -> bool:
    w3 = tx.token.collection.network.get_web3_connection()
    transaction = w3.eth.getTransactionReceipt(tx.tx_hash)
    logger.info(f"Transaction status success - {bool(transaction.get('status'))}")
    return bool(transaction.get("status"))


def check_tron_transactions(tx) -> bool:
    provider = HttpProvider(tx.token.collection.network.endpoint)
    tron = Tron(
        full_node=provider,
        solidity_node=provider,
        event_server=provider,
        private_key=config.PRIV_KEY,
    )
    transaction = tron.trx.get_transaction(tx.tx_hash)
    logger.info(f"Transaction status success - {transaction['ret'][0]['contractRet']}")
    return str(transaction["ret"][0]["contractRet"]).lower() in ["0", "revert"]


def check_transaction_status(tx, network_type) -> Optional[bool]:
    try:
        if network_type == "ethereum":
            return check_ethereum_transactions(tx)
        elif network_type == "tron":
            return check_tron_transactions(tx)
    except Exception as e:
        logger.warning("Transaction not yet mined. Error: ", e)
        return None


@shared_task(name="transaction_tracker")
def transaction_tracker():
    # delete expired blockers
    now = timezone.now()
    delta = timedelta(seconds=config.TX_TRACKER_TIMEOUT)
    expired_tx_list = TransactionTracker.objects.filter(tx_hash__isnull=True).filter(
        created_at__lt=now - delta
    )
    id_list = expired_tx_list.values_list("token__id", flat=True)
    tokens = Token.objects.filter(id__in=id_list)
    tokens.update(selling=True)
    expired_tx_list.delete()

    # check transactions
    for network_type in Types._member_names_:
        tx_list = TransactionTracker.objects.filter(
            token__collection__network__network_type=network_type
        )
        for tx in tx_list:
            is_success = check_transaction_status(tx, network_type)
            if is_success is not None:
                if not is_success:
                    tx.item.selling = True
                    tx.item.save()
                tx.delete()


@app.task()
def import_opensea_collection(collection_address, network_name, collection):
    network = Network.objects.filter(name__iexact=network_name).first()
    opensea_import = OpenSeaImport(collection_address, network)
    opensea_import.save_in_db(collection)
