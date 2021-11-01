from scaners.base import ScannerABC
from scaners.eth.mixins import DeployMixin, ApproveMixin, BuyMixin, MintMixin


class Scanner(
    ScannerABC,
    DeployMixin,
    ApproveMixin,
    BuyMixin,
    MintMixin,
):
    EMPTY_ADDRESS = "0x0000000000000000000000000000000000000000"

    def save_last_block(self) -> None:
        # TODO: set last block number to redis
        ...

    def get_last_block(self) -> int:
        # TODO: get last block number from redis
        ...

    def get_last_block_network(self) -> int:
        return self.network.get_web3_connection().eth.blockNumber
