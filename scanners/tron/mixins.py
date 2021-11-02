import requests
from scanners.base import DeployData, BuyData, ApproveData, MintData


class DeployMixin:
    def get_events_deploy(self, last_checked_block, last_network_block):
        type_match = {
            'ERC721': ['fabric721_address', 'ERC721Made'],
            'ERC1155': ['fabric1155_address', 'ERC115Made'],
        }
        collection_data = type_match[self.contract_type]
        collection_address = getattr(self.network, collection_data[0])
        event_name = collection_data[1]
        url = self.build_tronapi_url(last_checked_block, last_network_block, collection_address, event_name)
        events = requests.get(url).json()['data']
        return events

    def parse_data_deploy(self, event) -> DeployData:
        return DeployData(
            collection_name=event["args"]["name"],
            address=self.network.wrap_in_checksum(["args"]["newToken"]),
            deploy_block=event["blockNumber"],
        )


class BuyMixin:
    def get_events_buy(self, last_checked_block, last_network_block):
        type_match = {
            'ERC721': ['exchange_address', 'ExchangeMadeErc721'],
            'ERC1155': ['exchange_address', 'ExchangeMadeErc1155'],
        }
        collection_data = type_match[self.contract_type]
        collection_address = getattr(self.network, collection_data[0])
        event_name = collection_data[1]
        url = self.build_tronapi_url(last_checked_block, last_network_block, collection_address, event_name)
        events = requests.get(url).json()['data']
        return events

    def parse_data_buy(event) -> BuyData:
        return BuyData(
            buyer=event["args"]["buyer"].lower(),
            seller=event["args"]["seller"],
            price=event["args"]["buyAmount"],
            amount=event["args"]["sellAmount"],
            tx_hash=event["transactionHash"].hex(),
            token_id=event["args"]["sellId"],
            collection_address=event["args"]["sellTokenAddress"],
        )


class ApproveMixin:
    def get_events_approve(self, last_checked_block, last_network_block):
        collection_address = self.contract.address
        event_name = 'Approval'
        url = self.build_tronapi_url(last_checked_block, last_network_block, collection_address, event_name)
        events = requests.get(url).json()['data']

        return events

    def parse_data_approve(event) -> ApproveData:
        return ApproveData(
            exchange=event["args"]["guy"],
            user=event["args"]["src"].lower(),
            wad=event["args"]["wad"],
        )


class MintMixin:
    def get_events_mint(self, last_checked_block, last_network_block):
        collection_address = self.contract.address
        event_name = 'Transfer'
        url = self.build_tronapi_url(last_checked_block, last_network_block, collection_address, event_name)
        events = requests.get(url).json()['data']
        return events

    def parse_data_mint(event) -> MintData:
        token_id = event["args"].get("tokenId")
        if token_id is None:
            token_id = event["args"].get("id")
        return MintData(
            token_id=token_id,
            new_owner=event["args"]["to"].lower(),
            old_owner=event["args"]["from"].lower(),
            tx_hash=event["transactionHash"].hex(),
            amount=event["args"]["value"],
        )
