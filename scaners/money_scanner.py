import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django
django.setup()

from multiprocessing import Process
from scaners import scaner
from contracts import EXCHANGE, WETH_CONTRACT
from dds.settings import EXCHANGE_ADDRESS


if __name__ == '__main__':
    exchange = {'address': EXCHANGE_ADDRESS, 'abi': EXCHANGE}
    Process(target=scaner, args=(exchange, 'ERC_721')).start()
    Process(target=scaner, args=(exchange, 'ERC_1155')).start()
    Process(target=scaner, args=(WETH_CONTRACT,)).start()
