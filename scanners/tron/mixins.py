import requests

from scanners.base import ApproveData, BuyData, DeployData, MintData


class DeployMixin:
    def get_events_deploy(self, last_checked_block, last_network_block):
        type_match = {
            "ERC721": ["fabric721_address", "ERC721Made"],
            "ERC1155": ["fabric1155_address", "ERC1155Made"],
        }
        collection_data = type_match[self.contract_type]
        collection_address = getattr(self.network, collection_data[0])
        event_name = collection_data[1]
        url = self.build_tronapi_url(
            last_checked_block,
            last_network_block,
            collection_address,
            event_name,
        )
        events = requests.get(url).json()["data"]
        return events

    def parse_data_deploy(self, event) -> DeployData:
        return DeployData(
            collection_name=event["result"]["name"],
            address=self.to_tron_address(event["result"]["newToken"]),
            deploy_block=event["block_number"],
        )


class BuyMixin:
    def get_events_buy(self, last_checked_block, last_network_block):
        type_match = {
            "ERC721": ["exchange_address", "ExchangeMadeErc721"],
            "ERC1155": ["exchange_address", "ExchangeMadeErc1155"],
        }
        collection_data = type_match[self.contract_type]
        collection_address = getattr(self.network, collection_data[0])
        event_name = collection_data[1]
        url = self.build_tronapi_url(
            last_checked_block,
            last_network_block,
            collection_address,
            event_name,
        )
        events = requests.get(url).json()["data"]
        return events

    def parse_data_buy(self, event) -> BuyData:
        return BuyData(
            buyer=self.to_tron_address(event["result"]["buyer"]).lower(),
            seller=self.to_tron_address(event["result"]["seller"]).lower(),
            price=event["result"]["buyAmount"],
            amount=event["result"]["sellAmount"],
            tx_hash=event["transaction_id"],
            token_id=event["result"]["sellId"],
            collection_address=self.to_tron_address(
                event["result"]["sellTokenAddress"]
            ).lower(),
        )


class ApproveMixin:
    def get_events_approve(self, last_checked_block, last_network_block):
        collection_address = self.contract.address
        event_name = "Approval"
        url = self.build_tronapi_url(
            last_checked_block,
            last_network_block,
            collection_address,
            event_name,
        )
        events = requests.get(url).json()["data"]

        return events

    def parse_data_approve(self, event) -> ApproveData:
        return ApproveData(
            exchange=self.to_tron_address(event["result"]["guy"]).lower(),
            user=self.to_tron_address(event["result"]["src"]).lower(),
            wad=event["result"]["wad"],
        )


class MintMixin:
    def get_events_mint(self, last_checked_block, last_network_block):
        collection_address = self.contract
        events = []
        for event_name in ("ERC721Transfer", "ERC1155TransferSingle"):
            url = self.build_tronapi_url(
                last_checked_block,
                last_network_block,
                collection_address,
                event_name,
            )
            events += requests.get(url).json()["data"]
        return events

    def parse_data_mint(self, event) -> MintData:
        result = event["result"]
        token_id = result.get("tokenId")
        if token_id is None:
            token_id = result.get("id")
        return MintData(
            token_id=token_id,
            new_owner=self.to_tron_address(result["to"]).lower(),
            old_owner=self.to_tron_address(result["from"]).lower(),
            tx_hash=event["transaction_id"],
            amount=result.get("value", 1),
            contract=self.to_tron_address(result["token"]).lower(),
        )
