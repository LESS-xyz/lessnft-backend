import ipfshttpclient
from web3 import Web3, HTTPProvider
from dds.settings import NETWORK_SETTINGS, IPFS_CLIENT
from contracts import ERC721_MAIN, ERC1155_MAIN


def create_ipfs(request):
    client = ipfshttpclient.connect(IPFS_CLIENT)
    name = request.data.get("name")
    description = request.data.get("description")
    media = request.FILES.get("media")
    cover = request.FILES.get("cover")
    attributes = request.data.get("details")
    file_res = client.add(media)
    ipfs_json = {
        "name": name,
        "description": description,
        "attributes": attributes,
    }
    if animation:
        cover = client.add(cover)
        ipfs_json['animation_url'] = f'https://ipfs.io/ipfs/{file_res["Hash"]}'
        ipfs_json['image'] = f'https://ipfs.io/ipfs/{cover["Hash"]}'
    else:
        ipfs_json['image'] = f'https://ipfs.io/ipfs/{file_res["Hash"]}'
    res = client.add_json(ipfs_json)
    return res

def send_to_ipfs(media):
    client = ipfshttpclient.connect(IPFS_CLIENT)
    file_res = client.add(media)
    return file_res["Hash"]

def get_ipfs(token_id, address, standart) -> dict:
    """
    return ipfs by token

    :param token_id: token internal id
    :param address: contract address
    :param standart: token standart
    """
    if token_id != None:
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS["ETH"]["endpoint"]))
        if standart == "ERC721":
            abi = ERC721_MAIN
        else:
            abi = ERC1155_MAIN
        myContract = web3.eth.contract(
            address=web3.toChecksumAddress(address),
            abi=abi,
        )
        ipfs = myContract.functions.tokenURI(token_id).call()
        return ipfs


def get_ipfs_by_hash(ipfs_hash) -> dict:
    """
    return ipfs by hash
    """
    client = ipfshttpclient.connect(IPFS_CLIENT)
    return client.get_json(ipfs_hash)
