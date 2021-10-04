import json
import ipfshttpclient
from web3 import Web3, HTTPProvider
from dds.settings import IPFS_CLIENT
from dds.settings import config
from contracts import ERC721_MAIN, ERC1155_MAIN


def create_ipfs(request):
    client = ipfshttpclient.connect(config.IPFS_CLIENT)
    name = request.data.get("name")
    description = request.data.get("description")
    media = request.FILES.get("media")
    cover = request.FILES.get("cover")
    attributes = request.data.get("details")
    if attributes:
        attributes = json.loads(attributes)
    file_res = client.add(media)
    ipfs_json = {
        "name": name,
        "description": description,
        "attributes": attributes,
    }
    if cover:
        cover_res = client.add(cover)
        ipfs_json['animation_url'] = f'https://ipfs.io/ipfs/{file_res["Hash"]}'
        ipfs_json['image'] = f'https://ipfs.io/ipfs/{cover_res["Hash"]}'
    else:
        ipfs_json['image'] = f'https://ipfs.io/ipfs/{file_res["Hash"]}'
    res = client.add_json(ipfs_json)
    return res

def send_to_ipfs(media):
    client = ipfshttpclient.connect(config.IPFS_CLIENT)
    file_res = client.add(media)
    return file_res["Hash"]

def get_ipfs(token_id, contract) -> dict:
    """
    return ipfs by token
    """
    return contract.functions.tokenURI(token_id).call()


def get_ipfs_by_hash(ipfs_hash) -> dict:
    """
    return ipfs by hash
    """
    client = ipfshttpclient.connect(config.IPFS_CLIENT)
    return client.get_json(ipfs_hash)
