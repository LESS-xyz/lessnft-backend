import logging
from datetime import datetime, timedelta

from django.conf import timezone
from celery import shared_task
from src.store.models import Bid, Status, Token, TransactionTracker, Tags
from src.networks.models import Types
from src.store.services.auction import end_auction
from web3.exceptions import TransactionNotFound
from tronapi import HttpProvider, Tron
from src.settings import config

logger = logging.getLogger('celery')

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
        updated_at__lte=datetime.today() - timedelta(hours=config.CLEAR_TOKEN_TAG_NEW_TIME),
    )
    for token in tokens:
        token.tags.remove(tag)


@shared_task(name="end_auction_checker")
def end_auction_checker():
    tokens = Token.objects.committed().filter(
        end_auction__lte=datetime.today(),
    )
    for token in tokens:
        end_auction(token)


@shared_task(name="incorrect_bid_checker")
def incorrect_bid_checker():
    bids = Bid.objects.committed()
    for bid in bids:
        user_balance = bid.token.currency.network.contract_call(
                method_type='read',
                contract_type='token',
                address=bid.token.currency.address,
                function_name='balanceOf',
                input_params=(bid.user.username,),
                input_type=('address',),
                output_types=('uint256',),
            )

        allowance = bid.token.currency.network.contract_call(
                method_type='read',
                contract_type='token',
                address=bid.token.currency.address,
                function_name='allowance',
                input_params=(
                    bid.user.username,
                    bid.token.currency.network.exchange_address
                ),
                input_type=('address', 'address'),
                output_types=('uint256',),
            )

        if user_balance < bid.amount * bid.quantity or allowance < bid.amount * bid.quantity:
            bid.state = Status.EXPIRED
            bid.save()

def check_ethereum_transactions(tx):
    w3 = tx.token.collection.network.get_web3_connection()
    try:
        transaction = w3.eth.getTransactionReceipt(tx.tx_hash)
        logger.info(f"Transaction status success - {bool(transaction.get('status'))}")
        return bool(transaction.get('status'))

    except TransactionNotFound:
        logger.info("Transaction not yet mined")
        return "not found"

def check_tron_transactions(tx):
    provider = HttpProvider(tx.token.collection.network.endpoint)
    tron = Tron(
            full_node=provider,
            solidity_node=provider,
            event_server=provider,
            private_key=config.PRIV_KEY,
        )
    try:
        transaction = tron.trx.get_transaction(tx.tx_hash)
        logger.info(f"Transaction status success - {transaction['ret'][0]['contractRet']}")
        return transaction['ret'][0]['contractRet']

    except ValueError:
        logger.info("Transaction not yet mined")
        return "not found"

@shared_task(name="transaction_tracker")
def transaction_tracker():
    #delete expired blockers
    now = timezone.now()
    delta = timedelta(seconds=config.TX_TRACKER_TIMEOUT)
    expired_tx_list = TransactionTracker.objects.filter(tx_hash__isnull=True).filter(created_at__lt=now-delta)
    id_list = expired_tx_list.values_list('token__id', flat=True)
    tokens = Token.objects.filter(id__in=id_list)
    tokens.update(selling=True)
    expired_tx_list.delete()

    # check transactions
    for type in Types._member_names_:
        tx_list = TransactionTracker.objects.filter(token__collection__network__network_type=type)
        for tx in tx_list:
            if type == 'ethereum':
                tx = check_ethereum_transactions(tx)
            elif type == 'tron':
                tx = check_tron_transactions(tx)
            if tx != "not found":
                if tx == 0 or tx == 'REVERT':
                    tx.item.selling = True
                    tx.item.save()
                tx.delete()
