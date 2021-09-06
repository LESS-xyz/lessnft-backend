import ipfshttpclient
from web3 import Web3, HTTPProvider
from dds.settings import IPFS_CLIENT
from dds.store.models import Token


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

def get_ipfs(token_id) -> dict:
    """
    return ipfs by token

    :param token_id: token internal id
    :param address: contract address
    :param standart: token standart
    """
    if token_id != None:
        token = Token.objects.get(id=token_id)
        web3, contract = self.get_main_contract()
        ipfs = contract.functions.tokenURI(token_id).call()
        return ipfs


def get_ipfs_by_hash(ipfs_hash) -> dict:
    """
    return ipfs by hash
    """
    client = ipfshttpclient.connect(IPFS_CLIENT)
    return client.get_json(ipfs_hash)
