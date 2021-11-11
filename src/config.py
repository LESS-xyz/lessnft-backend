
import os
import yaml
from dataclasses import dataclass, field
from enum import Enum
from typing import List
from marshmallow_dataclass import class_schema


class NetworkType(Enum):
    ethereum = 'Ethereum'
    tron = 'Tron'

@dataclass
class Network:
    name: str
    needs_middlware: bool
    native_symbol: str
    endpoint: str
    fabric721_address: str
    fabric1155_address: str
    exchange_address: str
    network_type: NetworkType = field(metadata={"by_value": True})

@dataclass
class Config:
    EMAIL_HOST: str
    MAIL: str
    HOST_USER: str
    HOST_PASSWORD: str
    EMAIL_PORT: int
    EMAIL_USE_TLS: bool
    ALLOWED_HOSTS: list
    SECRET_KEY: str
    DEBUG: bool

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

    @dataclass
    class UsdRate:
       # rate: float
        coin_node: str
        symbol: str
        name: str
        image: str
        #updated_at: str
        address: str
        decimal: int
        network: int
        fee_discount: int
    
    @dataclass
    class MasterUser:
        address: str
        network: int
        commission: int
    
    @dataclass
    class Intervals:
        every: int
        period: str
    
    @dataclass
    class PeriodicTasks:
        name: str
        task: str
        interval: int
        enabled: bool

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

    API_URL: str

    RATES_CHECKER_TIMEOUT: int

    TITLE: str
    DESCRIPTION: str

    NETWORKS: List[Network]
    USD_RATES: List[UsdRate]
    MASTER_USER: MasterUser

    INTERVALS: List[Intervals]
    PERIODIC_TASKS: List[PeriodicTasks]

    REDIS_HOST: str
    REDIS_PORT: int


with open(os.path.dirname(__file__) + '/../config.yaml') as f:
    config_data = yaml.safe_load(f)

config: Config = class_schema(Config)().load(config_data)