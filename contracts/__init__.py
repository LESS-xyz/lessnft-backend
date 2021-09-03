import json
from pathlib import Path

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
