import json
from pathlib import Path
from web3 import Web3, HTTPProvider

from django.conf import settings

with Path("contracts", "erc721_fabric.json").open() as f:
    ERC721_FABRIC = json.load(f)

with Path("contracts", "erc1155_fabric.json").open() as f:
    ERC1155_FABRIC = json.load(f)

with Path("contracts", "exchange.json").open() as f:
    EXCHANGE = json.load(f)

with Path("contracts", "weth.json").open() as f:
    WETH_ABI = json.load(f)

with Path("contracts", "erc721_main.json").open() as f:
    ERC721_MAIN = json.load(f)

with Path("contracts", "erc1155_main.json").open() as f:
    ERC1155_MAIN = json.load(f)

w3 = Web3(HTTPProvider(settings.NETWORK_SETTINGS['ETH']['endpoint']))

ERC721_FABRIC_CONTRACT = w3.eth.contract(
    address=Web3.toChecksumAddress(settings.ERC721_FABRIC_ADDRESS),
    abi=ERC721_FABRIC
)

ERC1155_FABRIC_CONTRACT = w3.eth.contract(
    address=Web3.toChecksumAddress(settings.ERC1155_FABRIC_ADDRESS),
    abi=ERC1155_FABRIC
)

EXCHANGE_CONTRACT = w3.eth.contract(
    address=Web3.toChecksumAddress(settings.EXCHANGE_ADDRESS),
    abi=EXCHANGE
)

WETH_CONTRACT = w3.eth.contract(
    address=Web3.toChecksumAddress(settings.WETH_ADDRESS),
    abi=WETH_ABI
)