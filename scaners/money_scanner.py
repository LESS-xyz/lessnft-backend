import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django
django.setup()

from multiprocessing import Process
from scaners import scaner
from contracts import EXCHANGE, WETH_CONTRACT


if __name__ == '__main__':

    Process(target=scaner, args=(EXCHANGE, 'ERC_721')).start()
    Process(target=scaner, args=(EXCHANGE, 'ERC_1155')).start()
    Process(target=scaner, args=(WETH_CONTRACT,)).start()
