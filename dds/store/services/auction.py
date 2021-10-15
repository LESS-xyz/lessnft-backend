from web3 import Web3, HTTPProvider

from dds.settings import config
from contracts import EXCHANGE
from dds.store.models import Bid
   

def end_auction(token):
    bet = Bid.objects.filter(token=token).order_by("-amount").last()
    initial_tx = token.buy_token(0, bet.user, seller=token.owner, price=bet.amount)
    data = initial_tx.get("data")

    tx_params = {
        'chainId': initial_tx.get("chainId"),
        'gas': initial_tx.get("gas"), 
        'nonce': initial_tx.get("nonce"),
        'gasPrice': initial_tx.get("gasPrice"),
    }

    web3, contract = token.collection.network.get_exchage_contract()

    tx = contract.functions.makeExchangeERC721(
        idOrder = data.get("idOrder"),
        SellerBuyer = [
            token.collection.network.wrap_in_checksum(data.get("SellerBuyer")[0]),
            token.collection.network.wrap_in_checksum(data.get("SellerBuyer")[1]),
        ],
        tokenToBuy = {
            "tokenAddress": token.collection.network.wrap_in_checksum(data.get("tokenToBuy").get("tokenAddress")),
            "id": int(data.get("tokenToBuy").get("id")),
            "amount": int(data.get("tokenToBuy").get("amount")),
        },
        tokenToSell = {
            "tokenAddress": token.collection.network.wrap_in_checksum(data.get("tokenToSell").get("tokenAddress")),
            "id": int(data.get("tokenToSell").get("id")),
            "amount": int(data.get("tokenToSell").get("amount")),
        },
        feeAddresses = [
            token.collection.network.wrap_in_checksum(data.get("fee").get("feeAddresses")[0]),
            token.collection.network.wrap_in_checksum(data.get("fee").get("feeAddresses")[1]),
        ],
        feeAmounts = [
            int(data.get("fee").get("feeAddresses"))[0],
            int(data.get("fee").get("feeAddresses"))[1],
        ],
        signature = data.get("signature"),
    ).buildTransaction(tx_params)
    signed_tx = web3.eth.account.sign_transaction(tx, config.PRIV_KEY)
    tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)
    print(f"Auction for token {token} ended. Tx hash: {tx_hash.hex()}")
