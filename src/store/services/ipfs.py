import logging
import json

import ipfshttpclient
from src.settings import config
from django.apps import apps


def create_ipfs(request):
    logging.info(f'request:  {request.__dict__}')
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

def get_ipfs(token_id, collection) -> dict:
    """
    return ipfs by token
    """
    return collection.network.contract_call(
            method_type='read',
            contract_type=f'{collection.standart.lower()}main',
            address=collection.address,
            function_name='tokenURI',
            input_params=(int(token_id),),
            input_type=('uint256',),
            output_types=('string',),
    )


def get_ipfs_by_hash(ipfs_hash) -> dict:
    """
    return ipfs by hash
    """
    client = ipfshttpclient.connect(config.IPFS_CLIENT)
    return client.get_json(ipfs_hash)
