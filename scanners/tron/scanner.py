from tronapi import HttpProvider, Tron

from scanners.base import ScannerABC
from scanners.tron.mixins import ApproveMixin, BuyMixin, DeployMixin, MintMixin


class Scanner(
    ScannerABC,
    DeployMixin,
    ApproveMixin,
    BuyMixin,
    MintMixin,
):
    EMPTY_ADDRESS = "t9yd14nj9j7xab4dbgeix9h8unkkhxuwwb"

    def get_tron_instance(self):
        provider = HttpProvider(self.network.endpoint())
        return Tron(
            full_node=provider,
            solidity_node=provider,
            event_server=provider,
        )

    def build_tronapi_url(
        self, last_checked_block, last_network_block, collection_address, event_name
    ):
        last_checked_block_timestamp = self.get_block_timestamp(last_checked_block)
        last_network_block_timestamp = self.get_block_timestamp(last_network_block)
        url = (
            f"{self.network.endpoint()}/v1/contracts/{collection_address}/events?event_name={event_name}"
            f"&min_block_timestamp={last_checked_block_timestamp}"
            f"&max_block_timestamp={last_network_block_timestamp}"
        )
        return url

    def get_block_timestamp(self, number):
        tron = self.get_tron_instance()
        return tron.trx.get_block(number)["block_header"]["raw_data"]["timestamp"]

    def get_last_network_block(self):
        tron = self.get_tron_instance()
        return tron.trx.get_block("latest")["block_header"]["raw_data"]["number"]

    def to_tron_address(self, address):
        tron = Tron()
        return tron.address.from_hex(address.replace("0x", "41")).decode()
