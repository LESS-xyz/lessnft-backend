import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dds.settings')
import django
django.setup()

from multiprocessing import Process
from scaners import scaner
from dds.networks.models import Network
from dds.rates.models import UsdRate


if __name__ == '__main__':
    networks = Network.objects.all()
    rates = UsdRate.objects.all()
    for network in networks:
        web3, contract = network.get_exchage_contract()
        Process(target=scaner, args=(web3, contract, network.name, 'ERC_721', 'exchange')).start()
        Process(target=scaner, args=(web3, contract, network.name, 'ERC_1155', 'exchange')).start()
    for rate in rates:
        web3, contract = rate.network.get_token_contract(rate.address)
        Process(target=scaner, args=(web3, contract, rate.network.name, None, 'currency')).start()
