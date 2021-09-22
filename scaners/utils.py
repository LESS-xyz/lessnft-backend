import os
from web3 import Web3
from dds.networks.models import Network
base_dir = 'blocks'

def get_last_block(name, network_name) -> int:
    try:
        with open(os.path.join(base_dir, name), 'r') as file:
            last_block_number = file.read()
    except FileNotFoundError:
        network = Network.objects.get(name=network_name)
        w3 = network.get_web3_connection()
        last_block_number = w3.eth.block_number
        save_last_block(last_block_number, name)

    return int(last_block_number)

def save_last_block(last_block_number, network_name):
    with open(os.path.join(base_dir, network_name), 'w') as file:
        file.write(str(last_block_number))
