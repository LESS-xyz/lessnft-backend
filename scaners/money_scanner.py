import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django
django.setup()

from multiprocessing import Process
from scaners import scaner
from contracts import EXCHANGE_CONTRACT, WETH_CONTRACT
from dds.settings import EXCHANGE_ADDRESS


if __name__ == '__main__':
    Process(target=scaner, args=(EXCHANGE_CONTRACT, 'ERC_721', 'exchange')).start()
    Process(target=scaner, args=(EXCHANGE_CONTRACT, 'ERC_1155', 'exchange')).start()
    Process(target=scaner, args=(WETH_CONTRACT, None, 'currency')).start()
