import logging

from web3.exceptions import TransactionNotFound

from src.settings import config
from src.store.models import Bid


def end_auction(token):
    bet = Bid.objects.committed().filter(token=token).order_by("-amount").last()
    tx = token.buy_token(
        token_amount=0, buyer=bet.user, seller=token.owner, price=bet.amount, auc=True
    )
    web3 = token.collection.network.web3

    # TODO rework for tron
    signed_tx = web3.eth.account.sign_transaction(tx, config.PRIV_KEY)
    tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)
    print(f"Auction for token {token} ended. Tx hash: {tx_hash.hex()}")
    return tx_hash, token.collection.network


def check_auction_tx(tx_hash, network):
    while True:
        try:
            receipt = network.web3.eth.getTransactionReceipt(tx_hash)
        except TransactionNotFound:
            logging.info(f"Transaction with hash {tx_hash} not found")
            continue
        if receipt["status"] == 1:
            logging.info(f"Transaction with hash {tx_hash} completed")
        elif receipt["status"] == 0:
            logging.error(f"Transaction with hash {tx_hash} failed")
        return
