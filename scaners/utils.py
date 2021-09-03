import os
from web3 import Web3
base_dir = 'blocks'

def get_last_block(network_name) -> int:
    try:
        with open(os.path.join(base_dir, network_name), 'r') as file:
            last_block_number = file.read()
    except FileNotFoundError:
        last_block_number = Web3(Web3.HTTPProvider('https://rinkeby.infura.io/v3/7b0399b88fc74f07ac9318ce9fc7f855')).eth.block_number
        save_last_block(last_block_number, network_name)
        get_last_block(network_name)

    return int(last_block_number)

def save_last_block(last_block_number, network_name):
    with open(os.path.join(base_dir, network_name), 'w') as file:
        file.write(str(last_block_number))
