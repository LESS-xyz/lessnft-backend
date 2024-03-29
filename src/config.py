import os
from dataclasses import dataclass
from typing import List, Optional

import yaml
from marshmallow_dataclass import class_schema


@dataclass
class Network:
    name: str
    needs_middleware: bool
    native_symbol: str
    fabric721_address: str
    fabric1155_address: str
    exchange_address: str
    network_type: str


@dataclass
class Provider:
    endpoint: str
    network: str


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
    IPFS_DOMAIN: str
    SCANNER_SLEEP: int
    ORACLE_ADDRESS: str

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
        coin_node: str
        symbol: str
        name: str
        image: str
        address: str
        decimal: int
        network: str
        fee_discount: int

    @dataclass
    class MasterUser:
        address: str
        network: str
        commission: int

    @dataclass
    class Intervals:
        every: int
        period: str
        pk: int

    @dataclass
    class PeriodicTasks:
        name: str
        task: str
        interval: int
        enabled: bool

    SORT_STATUSES: SortStatus

    SEARCH_TYPES: SearchType

    SIGNER_ADDRESS: str
    CAPTCHA_SECRET: Optional[str]
    CAPTCHA_URL: Optional[str]
    PRIV_KEY: str
    BOTS: dict

    DEFAULT_NETWORK: Optional[str]
    TX_TRACKER_TIMEOUT: int

    REDIS_EXPIRATION_TIME: int
    CLEAR_TOKEN_TAG_NEW_TIME: int

    API_URL: str
    OPENSEA_API: str

    RATES_CHECKER_TIMEOUT: int
    TRENDING_TRACKER_TIME: int

    TITLE: str
    DESCRIPTION: str
    ITEMS_PER_PAGE: int

    NETWORKS: List[Network]
    PROVIDERS: List[Provider]
    USD_RATES: List[UsdRate]
    MASTER_USER: List[MasterUser]

    INTERVALS: List[Intervals]
    PERIODIC_TASKS: List[PeriodicTasks]
    DEFAULT_COMMISSION: Optional[int]

    REDIS_HOST: str
    REDIS_PORT: int


config_path = "/../config.yaml"
if os.getenv("IS_TEST", False):
    config_path = "/../config.example.yaml"


with open(os.path.dirname(__file__) + config_path) as f:
    config_data = yaml.safe_load(f)

config: Config = class_schema(Config)().load(config_data)
