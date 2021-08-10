import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django
django.setup()

from multiprocessing import Process
from scaners import scaner
from dds.settings import ERC1155_FABRIC_ADDRESS
from contracts import ERC1155_FABRIC
from dds.store.models import Collection
import time


if __name__ == '__main__':

    Process(target=scaner, args=({'address': ERC1155_FABRIC_ADDRESS, 'abi': ERC1155_FABRIC})).start()

    c = Collection.objects.filter(standart='ERC1155')
    for i in c:
        Process(target=scaner, args=(i,)).start()

    while True:
        time.sleep(60)
        new_c = Collection.objects.filter(standart='ERC1155', address__isnull=False)

        diff_c = list(set(new_c) - set(c))
        if diff_c:
            for i in diff_c:
                Process(target=scaner, args=(i,)).start()
            c = new_c

