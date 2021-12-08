import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.accounts.models import AdvUser
from src.settings import config
from src.utilities import RedisClient

_log_format = (
    "%(asctime)s - [%(levelname)s] - %(filename)s (line %(lineno)d) - %(message)s"
)

_datetime_format = "%d.%m.%Y %H:%M:%S"

loggers = {}


class HandlerABC(ABC):
    def __init__(self, network, scanner, contract=None) -> None:
        self.network = network
        self.scanner = scanner
        self.contract = contract

        logger_name = f"scanner_{self.TYPE}_{self.network}"

        # This is necessary so that records are not duplicated.
        if not loggers.get(logger_name):
            loggers[logger_name] = self.get_logger(logger_name)
        self.logger = loggers.get(logger_name)

    def get_owner(self, owner_address: str) -> Optional[AdvUser]:
        try:
            user = AdvUser.objects.get(username__iexact=owner_address)
        except AdvUser.DoesNotExist:
            user = AdvUser.objects.create_user(username=owner_address)
        return user

    def get_file_handler(self, name):
        file_handler = logging.FileHandler(f"logs/{name}.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(_log_format, datefmt=_datetime_format)
        )
        return file_handler

    def get_stream_handler(self):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(_log_format, datefmt=_datetime_format)
        )
        return stream_handler

    def get_logger(self, name):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self.get_file_handler(name))
        logger.addHandler(self.get_stream_handler())
        return logger

    @abstractmethod
    def save_event(self) -> None:
        ...


class ScannerABC(ABC):
    def __init__(self, network, contract_type=None, contract=None):
        self.network = network
        self.contract_type = contract_type
        self.contract = contract

    def sleep(self) -> None:
        time.sleep(config.SCANNER_SLEEP)

    def save_last_block(self, name, block) -> None:
        redis_ = RedisClient()
        redis_.connection.set(name, block)

    def get_last_block(self, name) -> int:
        redis_ = RedisClient()
        last_block_number = redis_.connection.get(name)
        if not last_block_number:
            last_block_number = self.get_last_network_block()
            if not last_block_number:
                return None
            self.save_last_block(name, last_block_number)
        return int(last_block_number)

    @abstractmethod
    def get_last_network_block(self) -> int:
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
    contract: Optional[str]
