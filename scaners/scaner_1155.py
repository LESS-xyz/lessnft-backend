import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django
django.setup()

from multiprocessing import Process
from scaners import scaner
from contracts import ERC1155_FABRIC_CONTRACT
from dds.store.models import Collection
import time


if __name__ == '__main__':

    Process(target=scaner, args=(ERC1155_FABRIC_CONTRACT, None, 'fabric')).start()

    collections = Collection.objects.filter(standart='ERC1155', address__isnull=False)
    for i in collections:
        contract = i.get_contract()
        Process(target=scaner, args=(contract,)).start()

    while True:
        time.sleep(60)
        updated_collections = Collection.objects.filter(standart='ERC1155', address__isnull=False)

        new_collections = list(set(updated_collections) - set(collections))
        if new_collections:
            for i in new_collections:
                contract = i.get_contract()
                Process(target=scaner, args=(contract,)).start()
            collections = updated_collections

