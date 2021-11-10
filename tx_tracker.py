import os
import time
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings")
django.setup()

from src.settings import config
from src.store.models import TransactionTracker
from web3.exceptions import TransactionNotFound


if __name__ == "__main__":
    while True:
        tx_list = TransactionTracker.objects.all()
        for tx in tx_list:
            w3 = tx.token.collection.network.get_web3_connection()
            try:
                transaction = w3.eth.getTransactionReceipt(tx.tx_hash)
                print(f"Transaction status success - {bool(transaction.get('status'))}")
                if not transaction.get("status"):
                    tx.item.selling = True
                    tx.item.save()
                tx.delete()
            except TransactionNotFound:
                print("Transaction not yet mined")
                continue
        time.sleep(config.TX_TRACKER_TIMEOUT)
