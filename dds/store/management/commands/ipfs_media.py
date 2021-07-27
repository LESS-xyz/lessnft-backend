from django.db.models.signals import post_save
from django.core.management.base import BaseCommand

import ipfshttpclient
from web3 import Web3, HTTPProvider

from dds.settings_local import NETWORK_SETTINGS
from dds.store.services.ipfs import get_ipfs
from dds.store.models import Token, token_save_dispatcher


class Command(BaseCommand):
    help = "Transfer meida to ipfs"

    def handle(self, *args, **options):
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS["ETH"]["endpoint"]))
        tokens = Token.objects.filter(ipfs=None)  

        for token in tokens:
            ipfs = get_ipfs(token)
            if ipfs:
                ipfs = ipfs["media"]
                token.ipfs = ipfs
                post_save.disconnect(token_save_dispatcher, sender=Token)
                token.save(update_fields=["ipfs"])
                post_save.connect(token_save_dispatcher, sender=Token)
