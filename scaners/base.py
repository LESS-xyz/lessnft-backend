import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from dds.utilities import RedisValues


class HandlerABC(ABC):
    def __init__(self, network, scanner, contract=None) -> None:
        self.network = network
        self.scanner = scanner
        self.contract = contract

    @abstractmethod
    def get_events(self) -> list:
        ...

    @abstractmethod
    def save_event(self) -> None:
        ...


class ScannerABC(ABC):
    def __init__(self, network, contract_type):
        self.network = network
        self.contract_type = contract_type

    def sleep(self) -> None:
        # TODO: from config
        time.sleep(1)

    def save_last_block(self, name, block) -> None:
        RedisValues.set_value(name, block)

    def get_last_block(self, name) -> int:
        last_block_number = RedisValues.get_value(name)
        if not last_block_number:
            last_block_number = self.get_last_block_network()
            self.save_last_block(name, last_block_number)
        return int(last_block_number)


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
