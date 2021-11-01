import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from dds.accounts.models import AdvUser


class HandlerABC(ABC):
    def __init__(self, network, scanner, contract=None) -> None:
        self.network = network
        self.scanner = scanner
        self.contract = contract

    def get_owner(self, owner_address: str) -> Optional[AdvUser]:
        return AdvUser.objects.filter(username=owner_address).first()

    @abstractmethod
    def save_event(self) -> None:
        ...


class ScannerABC(ABC):
    def __init__(self, network, contract_type=None):
        self.network = network
        self.contract_type = contract_type

    def sleep(self) -> None:
        # TODO: from config
        time.sleep(1)

    def save_last_block(self) -> None:
        ...

    def get_last_block(self) -> int:
        ...

    @abstractmethod
    def get_last_block_network(self) -> int:
        ...


@dataclass
class DeployData:
    collection_name: str
    address: str
    deploy_block: int


@dataclass
class BuyData:
    buyer: str
    seller: str
    price: float
    amount: int
    token_id: int
    tx_hash: str
    collection_address: str


@dataclass
class ApproveData:
    exchange: str
    user: str
    wad: int


@dataclass
class MintData:
    token_id: int
    new_owner: str
    old_owner: str
    tx_hash: str
    amount: int
