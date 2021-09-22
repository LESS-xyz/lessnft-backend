import ipfshttpclient
from web3 import Web3, HTTPProvider
from dds.settings import IPFS_CLIENT
from django.apps import apps

def create_ipfs(request):
    client = ipfshttpclient.connect(IPFS_CLIENT)
    name = request.data.get("name")
    description = request.data.get("description")
    media = request.FILES.get("media")
    animation = request.FILES.get("animation")
    attributes = request.data.get("details")
    file_res = client.add(media)
    ipfs_json = {
        "name": name,
        "description": description,
        "image": f'https://ipfs.io/ipfs/{file_res["Hash"]}',
        "attributes": attributes,
    }
    if animation:
        anim_res = client.add(animation)
        ipfs_json['animation_url'] = f'https://ipfs.io/ipfs/{anim_res["Hash"]}'
    res = client.add_json(ipfs_json)
    return res

def send_to_ipfs(media):
    client = ipfshttpclient.connect(IPFS_CLIENT)
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
    client = ipfshttpclient.connect(IPFS_CLIENT)
    return client.get_json(ipfs_hash)
