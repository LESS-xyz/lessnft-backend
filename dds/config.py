
import os
import yaml
from dataclasses import dataclass, field
from marshmallow_dataclass import class_schema
'''
@dataclass
class ETH:
    endpoint: str


@dataclass
class NetworkSettings:
    ETH: ETH
    
@dataclass
class SortStatus:
    recent: str
    cheapest: str
    highest: str

@dataclass
class SearchType:
    items: str
    users: str
    collections: str

@dataclass
class Config:
    EMAIL_HOST: str
    DDS_MAIL: str
    DDS_HOST_USER: str
    DDS_HOST_PASSWORD: str
    EMAIL_PORT: int
    EMAIL_USE_TLS: bool
    ALLOWED_HOSTS: list
    IPFS_CLIENT: str

    ERC721_FABRIC_ADDRESS: str
    ERC1155_FABRIC_ADDRESS: str
    EXCHANGE_ADDRESS: str
    WETH_ADDRESS: str

    DEFAULT_AVATARS: list

    NETWORK_SETTINGS: NetworkSettings

    SORT_STATUSES: SortStatus

    SEARCH_TYPES: SearchType

    SIGNER_ADDRESS: str
    CAPTCHA_SECRET: str
    CAPTCHA_URL: str
    PRIV_KEY: str

    ERC20_ADDRESS: str

    COLLECTION_721: str
    COLLECTION_1155: str

    TX_TRACKER_TIMEOUT: int

    HOLDERS_CHECK_CHAIN_LENGTH: int
    HOLDERS_CHECK_COMMITMENT_LENGTH: int
    HOLDERS_CHECK_TIMEOUT: int


with open(os.path.dirname(__file__) + '/../config.yaml') as f:
    config_data = yaml.safe_load(f)

config: Config = class_schema(Config)().load(config_data)
'''
@dataclass
class Config:
    EMAIL_HOST: str
    DDS_MAIL: str
    DDS_HOST_USER: str
    DDS_HOST_PASSWORD: str
    EMAIL_PORT: int
    EMAIL_USE_TLS: bool
    ALLOWED_HOSTS: list

    IPFS_CLIENT: str

    @dataclass
    class SortStatus:
        recent: str
        cheapest: str
        highest: str

    @dataclass
    class SearchType:
        items: str
        users: str
        collections: str

    SORT_STATUSES: SortStatus

    SEARCH_TYPES: SearchType

    SIGNER_ADDRESS: str
    CAPTCHA_SECRET: str
    CAPTCHA_URL: str
    PRIV_KEY: str

    DEFAULT_NETWORK : str
    COLLECTION_721: str
    COLLECTION_1155: str

    TX_TRACKER_TIMEOUT: int

    HOLDERS_CHECK_CHAIN_LENGTH: int
    HOLDERS_CHECK_COMMITMENT_LENGTH: int
    HOLDERS_CHECK_TIMEOUT: int


with open(os.path.dirname(__file__) + '/../config.yaml') as f:
    config_data = yaml.safe_load(f)

config: Config = class_schema(Config)().load(config_data)
