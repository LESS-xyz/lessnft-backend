import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings")
import django

django.setup()

from scanners.scanners import (
    ScannerAbsolute,
    HandlerDeploy,
    HandlerBuy,
    HandlerApproveBet,
    HandlerMintTransferBurn,
)
from src.networks.models import Network
from src.rates.models import UsdRate
from src.store.models import Collection, Status
from src.settings import config

if __name__ == "__main__":
    networks = Network.objects.all()
    rates = UsdRate.objects.exclude(address='0xEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE')
    for network in networks:
        for standart in ["ERC721", "ERC1155"]:
        ##################################################
        #                  BUY SCANNER                   #
        ##################################################
            ScannerAbsolute(
                network=network, 
                handler=HandlerBuy,
                contract_type=standart,
            ).start()

        ##################################################
        #                 DEPLOY SCANNER                 #
        ##################################################
            ScannerAbsolute(
                network=network,
                contract_type=standart,
                handler=HandlerDeploy,
            ).start()

    ##################################################
    #               APPROVE BET SCANNER              #
    ##################################################
    for rate in rates:
        contract = rate.network.get_token_contract(rate.address)
        ScannerAbsolute(
            network=rate.network,
            handler=HandlerApproveBet,
            contract=contract,
        ).start()

    ##################################################
    #                  MINT SCANNER                  #
    ##################################################

    # Tron
    contract_address = config.ORACLE_ADDRESS
    network = Network.objects.filter(network_type="tron").first()
    ScannerAbsolute(
        network=network,
        handler=HandlerMintTransferBurn,
        contract=contract_address,
    ).start()

    # Ethereum
    collections = Collection.objects.filter(status__in=[Status.COMMITTED, Status.SYNCED]).exclude(network__network_type="tron")
    for collection in collections:
        ScannerAbsolute(
            network=collection.network,
            handler=HandlerMintTransferBurn,
            contract_type=collection.standart,
            contract=collection.get_contract()
        ).start()

    while True:
        time.sleep(60)
        updated_collections = Collection.objects.filter(status__in=[Status.COMMITTED, Status.SYNCED]).exclude(network__network_type="tron")
        new_collections = list(set(updated_collections) - set(collections))

        if new_collections:
            for collection in new_collections:
                block = None
                if collection.status == Status.SYNCED:
                    block = collection.deploy_block
                ScannerAbsolute(
                    network=collection.network,
                    handler=HandlerMintTransferBurn,
                    contract=collection.get_contract(),
                    contract_type=collection.standart,
                    block=block,
                ).start()
            collections = updated_collections
