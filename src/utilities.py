import logging

from django.utils import timezone
from datetime import timedelta

from eth_account import Account
from web3 import Web3
from typing import Tuple
import redis
from math import ceil

from src.settings import config


class RedisClient:
    def __init__(self):
        self.pool = redis.ConnectionPool(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=0,
        )

    def set_connection(self) -> None:
        self._conn = redis.Redis(connection_pool=self.pool)

    @property
    def connection(self):
        if not hasattr(self, "_conn"):
            self.set_connection()
        return self._conn


def sign_message(type, message):
    message_hash = Web3.soliditySha3(type, message)
    signed = Account.signHash(message_hash, config.PRIV_KEY)
    return signed["signature"].hex()


def get_media_from_ipfs(hash):
    if not hash:
        return None
    return "https://dev3-ipfs.rocknblock.io/ipfs/{ipfs}".format(ipfs=hash)


def get_page_slice(
    page: int, items_length: int = None, items_per_page: int = 50
) -> Tuple[int, int]:
    page = int(page)
    start = (page - 1) * items_per_page
    end = None
    if not items_length or items_length >= page * items_per_page:
        end = page * items_per_page
    return start, end


def get_periods(*args, **kwargs):
    from_date = kwargs.get("from_date") or timezone.now()
    PERIODS = {
        "day": from_date - timedelta(days=1),
        "week": from_date - timedelta(days=7),
        "month": from_date - timedelta(days=30),
        "year": from_date - timedelta(days=365),
    }
    periods = {}
    for key in args:
        periods[key] = PERIODS[key]
    return periods


class PaginateMixin:
    def _parse_request(self, request):
        try:
            self.page = abs(int(request.query_params.get("page", 1))) or 1
        except Exception as e:
            logging.error(f"Pagination value error {e}")
            self.page = 1
        try:
            self.items_per_page = int(
                abs(request.query_params.get("items_per_page", config.ITEMS_PER_PAGE))
            ) or int(config.ITEMS_PER_PAGE)
        except Exception as e:
            logging.error(f"Pagination value error {e}")
            self.items_per_page = int(config.ITEMS_PER_PAGE)

    def get_page_slice(self, items_length: int) -> Tuple[int, int]:
        start = (self.page - 1) * self.items_per_page
        end = None
        if not items_length or items_length >= self.page * self.items_per_page:
            end = self.page * self.items_per_page
        return start, end

    def paginate(self, request, items):
        self._parse_request(request)
        start, end = self.get_page_slice(len(items))
        pages = len(items) / self.items_per_page
        return {
            "total": len(items),
            "results_per_page": self.items_per_page,
            "total_pages": ceil(pages),
            "results": items[start:end],
        }
