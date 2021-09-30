import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django
django.setup()

# from multiprocessing import Process
import threading
from scaners import scaner
from dds.store.models import Collection
from dds.networks.models import Network
import time


if __name__ == '__main__':
    networks = Network.objects.all()
    network_collections={}
    for network in networks:
        web3, contract = network.get_erc721fabric_contract()
        threading.Thread(target=scaner, args=(web3, contract, network.name, None, 'fabric')).start()

        collections = Collection.objects.filter(standart='ERC721', network=network, address__isnull=False)
        for i in collections:
            web3, contract = i.get_contract()
            threading.Thread(target=scaner, args=(web3, contract,)).start()
        network_collections[network.name] = collections

    while True:
        # get new collections and add them to subthreading.Threades
        time.sleep(60)
        for network in networks:
            updated_collections = Collection.objects.filter(standart='ERC721', network=network, address__isnull=False)

            new_collections = list(set(updated_collections) - set(network_collections[network.name]))
            if new_collections:
                for i in new_collections:
                    web3, contract = i.get_contract()
                    threading.Thread(target=scaner, args=(web3, contract,)).start()
                network_collections[network.name] = updated_collections

