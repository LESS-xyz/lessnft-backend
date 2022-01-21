import logging
from typing import TYPE_CHECKING

import requests
from django.db import models
from eth_abi import decode_abi, encode_abi
from tronapi import HttpProvider, Tron
from tronapi.common.account import Address as TronAddress
from trx_utils import decode_hex
from web3 import Web3

from contracts import (
    ERC721_FABRIC,
    ERC721_MAIN,
    ERC1155_FABRIC,
    ERC1155_MAIN,
    EXCHANGE,
    WETH_ABI,
)
from src.networks.utils import tron_function_selector
from src.settings import config

if TYPE_CHECKING:
    from web3.contract import Contract
    from web3.types import ABI


class Types(models.TextChoices):
    ethereum = "ethereum"
    tron = "tron"


class Address:
    def __init__(self, address):
        self.address = address


class Network(models.Model):
    """
    Represent different networks as different blockchains,
    in witch we have our contracts.
    """

    icon = models.CharField(max_length=200, blank=True, null=True, default=None)
    name = models.CharField(max_length=100)
    needs_middleware = models.BooleanField(default=False)
    native_symbol = models.CharField(max_length=10, blank=True, null=True, default=None)
    fabric721_address = models.CharField(max_length=128)
    fabric1155_address = models.CharField(max_length=128)
    exchange_address = models.CharField(max_length=128)
    network_type = models.CharField(
        max_length=20,
        choices=Types.choices,
        default=Types.ethereum,
    )

    def __str__(self):
        return self.name

    @property
    def ipfs_icon(self):
        if self.icon:
            return "https://ipfs.io/ipfs/{ipfs}".format(ipfs=self.icon)

    @property
    def web3(self):
        return Web3(
            Web3.HTTPProvider(self.providers.all().values_list("endpoint", flat=True))
        )

    def endpoint(self) -> str:
        """Need for TRON methods"""
        return self.providers.first().endpoint

    def _get_contract_by_abi(self, abi: "ABI", address: str = None) -> "Contract":
        if address:
            address = self.wrap_in_checksum(address)
        contract = self.web3.eth.contract(address=address, abi=abi)
        return contract

    def get_exchange_contract(self) -> "Contract":
        return self._get_contract_by_abi(EXCHANGE, self.exchange_address)

    def get_erc721fabric_contract(self) -> "Contract":
        return self._get_contract_by_abi(ERC721_FABRIC, self.fabric721_address)

    def get_erc1155fabric_contract(self) -> "Contract":
        return self._get_contract_by_abi(ERC1155_FABRIC, self.fabric1155_address)

    def get_erc721main_contract(self, address: str = None) -> "Contract":
        if self.network_type == Types.ethereum:
            return self._get_contract_by_abi(ERC721_MAIN, address)
        return Address(address)

    def get_erc1155main_contract(self, address: str = None) -> "Contract":
        if self.network_type == Types.ethereum:
            return self._get_contract_by_abi(ERC1155_MAIN, address)
        return Address(address)

    def get_token_contract(self, address: str = None) -> "Contract":
        if self.network_type == Types.ethereum:
            return self._get_contract_by_abi(WETH_ABI, address)
        return Address(address)

    def get_last_block(self) -> int:
        return self.web3.eth.block_number

    def get_ethereum_address(self, address):
        if self.network_type == Types.tron:
            return self.web3.toChecksumAddress("0x" + TronAddress.to_hex(address)[2:])
        return self.web3.toChecksumAddress(address)

    def wrap_in_checksum(self, address: str) -> str:
        """Wrap address to checksum because calling web3 for tron will return an error"""
        if self.network_type == Types.ethereum:
            return self.web3.toChecksumAddress(address)
        return address

    def contract_call(self, method_type: str, **kwargs):
        """
        redirects to ethereum/tron/whatever_functional_we_will_add_later read/write method
        kwargs example for ethereum/tron read method:
        {
        address: str, #address of contract if necessary
        contract_type: str, #contract type for calling web3 instance via get_{contract_type}_method()
        function_name: str, #function name for function selector
        input_types: tuple, #tuple of function param types (i.e. ('address', 'uint256')) for stupid tron
        input_params: tuple, #tuple of function param values
        output_types: tuple, #tuple of output param types if necessary (for stupid tron)
        is1155: boolean, #boolean for frontend to determine contract standart
        }
        """
        return getattr(self, f"execute_{self.network_type}_{method_type}_method")(
            **kwargs
        )

    def execute_ethereum_read_method(self, **kwargs):
        contract_type = kwargs.get("contract_type")
        address = kwargs.get("address")
        function_name = kwargs.get("function_name")
        input_params = kwargs.get("input_params")
        # don't like this if-else , TODO refactor
        if contract_type in ("exchange", "erc721fabric", "erc1155fabric"):
            contract = getattr(self, f"get_{contract_type}_contract")()
        else:
            contract = getattr(self, f"get_{contract_type}_contract")(address)
        # to not send None into function args
        if input_params:
            return getattr(contract.functions, function_name)(*input_params).call()
        return getattr(contract.functions, function_name)().call()

    def execute_ethereum_write_method(self, **kwargs):
        contract_type = kwargs.get("contract_type")
        address = kwargs.get("address")
        send = kwargs.get("send", False)
        if address:
            contract = getattr(self, f"get_{contract_type}_contract")(address)
        else:
            contract = getattr(self, f"get_{contract_type}_contract")()

        gas_limit = kwargs.get("gas_limit")
        nonce_username = kwargs.get("nonce_username")
        if send:
            nonce_username = config.SIGNER_ADDRESS
        tx_value = kwargs.get("tx_value")
        assert gas_limit is not None
        assert nonce_username is not None

        tx_params = {
            "chainId": self.web3.eth.chainId,
            "gas": gas_limit,
            "nonce": self.web3.eth.getTransactionCount(
                self.wrap_in_checksum(nonce_username), "pending"
            ),
            "gasPrice": self.web3.eth.gasPrice,
        }
        if tx_value is not None:
            tx_params["value"] = tx_value

        function_name = kwargs.get("function_name")
        input_params = kwargs.get("input_params")
        # to not send None into function args
        if input_params:
            initial_tx = getattr(contract.functions, function_name)(
                *input_params
            ).buildTransaction(tx_params)
        else:
            initial_tx = getattr(contract.functions, function_name)().buildTransaction(
                tx_params
            )
        if send:
            signed_tx = self.web3.eth.account.sign_transaction(
                initial_tx, config.PRIV_KEY
            )
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
            return tx_hash.hex()
        return initial_tx

    def execute_tron_read_method(self, **kwargs):
        input_params = kwargs.get("input_params")
        input_types = kwargs.get("input_type")
        function_name = kwargs.get("function_name")
        output_types = kwargs.get("output_types")
        address = kwargs.get("address")
        contract_type = kwargs.get("contract_type")

        input_data = encode_abi(input_types, input_params).hex()
        address_match = {
            "exchange": "exchange_address",
            "erc721fabric": "fabric721_address",
            "erc1155fabric": "fabric1155_address",
        }
        if not address:
            address = getattr(self, address_match.get(contract_type))
            if not address:
                logging.error(
                    f"could not get contract address for {contract_type} in {self.name}"
                )
                raise "backend didn't found contract address"
        address = TronAddress.to_hex(address)
        function = tron_function_selector(function_name, input_types)
        if len(input_params) == 1:
            function = function.replace(",", "")
        payload = {
            # "visible": True,
            "owner_address": config.SIGNER_ADDRESS.replace("0x", "41"),
            "contract_address": address,
            "function_selector": function,
            "parameter": input_data,
        }
        logging.info(payload)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        url = self.endpoint() + "/wallet/triggerconstantcontract"
        response = requests.post(url, json=payload, headers=headers)
        logging.info(response.json())
        constant_result = response.json()["constant_result"][0]
        decoded_data = decode_hex(constant_result)
        result = decode_abi(output_types, decoded_data)
        return result[0]

    def execute_tron_write_method(self, **kwargs):
        input_params = kwargs.get("input_params")
        input_types = kwargs.get("input_type")
        function_name = kwargs.get("function_name")
        address = kwargs.get("address")
        contract_type = kwargs.get("contract_type")
        tx_value = kwargs.get("tx_value")
        is1155 = kwargs.get("is1155")
        if not tx_value:
            tx_value = 0
        send = kwargs.get("send", False)
        logging.info(f"{contract_type}, {address}")
        address_match = {
            "exchange": "exchange_address",
            "erc721fabric": "fabric721_address",
            "erc1155fabric": "fabric1155_address",
        }
        if not address:
            address = getattr(self, address_match.get(contract_type))
            if not address:
                logging.info(
                    f"could not get contract address for {contract_type} in {self.name}"
                )
                raise "backend didn't found contract address"
        provider = HttpProvider(self.endpoint())
        tron = Tron(
            full_node=provider,
            solidity_node=provider,
            event_server=provider,
            private_key=config.PRIV_KEY,
        )
        tron.private_key = config.PRIV_KEY
        signer_address = tron.address.from_private_key(tron.private_key).base58
        tron.default_address = signer_address
        params = []
        for i in range(len(input_params)):
            if input_types[i] in ("bytes", "bytes32") and send:
                params.append(
                    {
                        "type": input_types[i],
                        "value": tron.toBytes(hexstr=input_params[i]),
                    }
                )
            else:
                params.append({"type": input_types[i], "value": input_params[i]})

        logging.info(input_params)
        logging.info(params)

        options = {
            "feeLimit": 1000000000,
            # TODO set callValue (for goddamn native buying)
            "callValue": tx_value,
            "tokenValue": 0,
            "tokenId": 0,
        }

        initial_tx = {
            "contractAddress": address,
            "function": tron_function_selector(function_name, input_types),
            "fee_limit": 1000000000,
            "options": options,
            "parameter": params,
        }
        if function_name in ("transferFrom", "safeTransferFrom", "burn"):
            initial_tx["is1155"] = is1155

        logging.info(params)

        if send:
            initial_tx = tron.transaction_builder.trigger_smart_contract(
                contract_address=address,
                function_selector=tron_function_selector(function_name, input_types),
                fee_limit=1000000000,
                call_value=0,
                parameters=params,
            )["transaction"]
            signed = tron.trx.sign(initial_tx)
            tx_hash = tron.trx.broadcast(signed)["txid"]
            return tx_hash
        logging.info(initial_tx)
        return initial_tx

    """
    TODO: запихнуть в поля модели
    """

    @property
    def check_timeout(self) -> int:
        return 6


class Provider(models.Model):
    endpoint = models.CharField(max_length=256)
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        related_name="providers",
    )

    def __str__(self):
        return self.endpoint


def collection_created_dispatcher(sender, instance, created, **kwargs):
    if created:
        MasterUser.objects.create(
            network=instance, commission=config.DEFAULT_COMMISSION
        )


post_save.connect(collection_created_dispatcher, sender=Network)
