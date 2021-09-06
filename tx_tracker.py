import os
import time
import django

from web3.exceptions import TransactionNotFound
from web3 import Web3, HTTPProvider

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dds.settings")
django.setup()

from dds import settings
from dds.store.models import TransactionTracker


if __name__ == "__main__":
    while True:
        tx_list = TransactionTracker.objects.all()
        w3 = Web3(HTTPProvider(settings.NETWORK_SETTINGS["ETH"]["endpoint"]))
        for tx in tx_list:
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
        time.sleep(settings.TX_TRACKER_TIMEOUT)
