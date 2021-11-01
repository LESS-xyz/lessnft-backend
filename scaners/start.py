import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dds.settings")
import django

django.setup()

from scaners.new_scanners import (
    ScannerAbsolute,
    HandlerDeploy,
    HandlerBuy,
    HandlerAprooveBet,
    HandlerMintTransferBurn,
)
from dds.networks.models import Network
from dds.rates.models import UsdRate
from dds.store.models import Collection


if __name__ == "__main__":
    networks = Network.objects.all()
    rates = UsdRate.objects.all()
    for network in networks:
        ##################################################
        #                  BUY SCANNER                   #
        ##################################################
        ScannerAbsolute(network=network, handler=HandlerBuy).run()

        ##################################################
        #                 DEPLOY SCANNER                 #
        ##################################################
        for standart in ["ERC721", "ERC1155"]:
            ScannerAbsolute(
                network=network,
                contract_type=standart,
                handler=HandlerDeploy,
            ).run()

    ##################################################
    #               APPROVE BET SCANNER              #
    ##################################################
    for rate in rates:
        _, contract = rate.network.get_token_contract(rate.address)
        ScannerAbsolute(
            network=network,
            handler=HandlerAprooveBet,
            contract=contract,
        ).run()

    ##################################################
    #                  MINT SCANNER                  #
    ##################################################
    collections = Collection.objects.committed()
    for collection in collections:
        ScannerAbsolute(
            network=network,
            handler=HandlerMintTransferBurn,
            contract_type=collection.standart,
        ).run()

    while True:
        time.sleep(60)
        for network in networks:
            updated_collections = Collection.objects.committed()
            new_collections = list(set(updated_collections) - set(collections))

            if new_collections:
                for collection in new_collections:
                    ScannerAbsolute(
                        network=network,
                        handler=HandlerMintTransferBurn,
                        contract_type=collection.standart,
                    ).run()
                collections = updated_collections
