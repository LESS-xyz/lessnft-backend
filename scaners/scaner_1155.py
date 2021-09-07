import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django
django.setup()

from multiprocessing import Process
from scaners import scaner
from dds.store.models import Collection
from dds.networks.models import Network
import time


if __name__ == '__main__':
    collections = Collection.objects.filter(standart='ERC1155', address__isnull=False)
    networks = Network.objects.all()
    for network in networks:
        web3, contract = network.get_erc1155fabric_contract()
        Process(target=scaner, args=(web3, contract, None, 'fabric')).start()

    for i in collections:
        web3, contract = i.get_contract()
        Process(target=scaner, args=(web3, contract,)).start()

    while True:
        time.sleep(60)
        updated_collections = Collection.objects.filter(standart='ERC1155', address__isnull=False)

        new_collections = list(set(updated_collections) - set(collections))
        if new_collections:
            for i in new_collections:
                web3, contract = i.get_contract()
                Process(target=scaner, args=(web3, contract,)).start()
            collections = updated_collections
