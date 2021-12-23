from src.store.models import Bid
from src.settings import config


def end_auction(token):
    bet = Bid.objects.committed().filter(token=token).order_by("-amount").last()
    tx = token.buy_token(
        token_amount=0, buyer=bet.user, seller=token.owner, price=bet.amount, auc=True
    )
    web3 = token.collection.network.get_web3_connection()

    # TODO rework for tron
    signed_tx = web3.eth.account.sign_transaction(tx, config.PRIV_KEY)
    tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)

    print(f"Auction for token {token} ended. Tx hash: {tx_hash.hex()}")
