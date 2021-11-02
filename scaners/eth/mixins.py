from scaners.base import DeployData, BuyData, ApproveData, MintData


class DeployMixin:
    def get_events_deploy(self, last_checked_block, last_network_block, contract=None):
        event = {
            "ERC721": self.network.get_erc721fabric_contract()[1].events.ERC721Made,
            "ERC1155": self.network.get_erc1155fabric_contract()[1].events.ERC1155Made,
        }[self.contract_type]
        return event.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

    def parse_data_deploy(self, event) -> DeployData:
        return DeployData(
            collection_name=event["args"]["name"],
            address=self.network.wrap_in_checksum(["args"]["newToken"]),
            deploy_block=event["blockNumber"],
        )


class BuyMixin:
    def get_events_buy(self, last_checked_block, last_network_block, contract=None):
        event = {
            "ERC721": self.network.get_exchange_contract()[1].events.ExchangeMadeErc721,
            "ERC1155": self.network.get_exchange_contract()[
                1
            ].events.ExchangeMadeErc1155,
        }[self.contract_type]
        return event.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

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
    def get_events_approve(self, last_checked_block, last_network_block, contract=None):
        return contract.events.Approval.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

    def parse_data_approve(event) -> ApproveData:
        return ApproveData(
            exchange=event["args"]["guy"],
            user=event["args"]["src"].lower(),
            wad=event["args"]["wad"],
        )


class MintMixin:
    def get_events_mint(self, last_checked_block, last_network_block, contract=None):
        event = {
            "ERC721": self.network.get_erc721main_contract(self.contract.address)[1].events.Transfer,
            "ERC1155": self.network.get_erc1155main_contract(self.contract.address)[1].events.TransferSingle,
        }[self.contract_type]
        return event.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

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
