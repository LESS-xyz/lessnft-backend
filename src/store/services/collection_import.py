import requests
import logging
from web3.exceptions import ContractLogicError
from src.store.models import Collection, Token, Status
from src.accounts.models import AdvUser
from dataclasses import dataclass, fields
from typing import Optional


URL = 'https://api.opensea.io/api/v1/'
logger = logging.getLogger('celery')


class OpenSeaAPI:
    def asset_contract(self, collection_address):
        return requests.get(f"{URL}asset_contract/{collection_address}/")

    def collection(self, collection_slug):
        return requests.get(f"{URL}collection/{collection_slug}/")

    def assets(self, address, offset=0, limit=50):
        assert limit <= 50, "The max limit in api is 50"

        return requests.get(f"{URL}assets/", params={
            "asset_contract_address": address,
            "offset": offset,
            "limit": limit,
        })


class OpenSeaImport:
    def __init__(self, collection_address, network):
        self.collection_address = collection_address
        self.network = network 
        self.api = OpenSeaAPI()

    def _get_collection_slug(self):
        response = self.api.asset_contract(self.collection_address)
        if response.status_code == 200:
            return response.json()["collection"]["slug"]

    def get_collection_data(self):
        """ Return collection data from opensea api """
        slug = self._get_collection_slug()
        if not slug:
            return None
        response = self.api.collection(slug)
        if response.status_code == 200:
            return response.json().get("collection")
        return None

    def save_in_db(self, collection):
        """ 
        Parse collection data and create 
        collection and tokens if not exists 
        """
        collection_model, _ = self.get_or_save_collection(collection)
        self.save_tokens(collection_model)

    def _get_user(self, user):
        """
        Parse user data and get or create user by username
        """
        if not user['user']:
            return None
        try:
            adv_user = AdvUser.objects.get(username__iexact=user['address'])
        except AdvUser.DoesNotExist:
            adv_user = AdvUser.objects.create_user(
                username=user['address'], 
                display_name=user['user']['username'],
                avatar_ipfs=user['profile_img_url'],
            )
        return adv_user

    def get_tokens_models(self, tokens, collection):
        """
        Check if token exists and valid
        and return list of Token instance
        """
        tokens = [TokenData(**token) for token in tokens]
        internal_ids = [token.token_id for token in tokens]
        internal_ids = list(Token.objects.filter(
            collection=collection, 
            internal_id__in=internal_ids,
        ).values_list("internal_id", flat=True))

        return [token.get_token_model(collection) for token in tokens if token.is_valid and token.token_id not in internal_ids]
    
    def save_tokens(self, collection):
        logger.info(f"Save tokens of {collection}")
        limit = 50
        offset = 0
        while True:
            response = self.api.assets(
                self.collection_address, 
                offset=offset * limit, 
                limit=limit,
            )
            if response.status_code != 200:
                return
            tokens = response.json().get("assets")
            if not tokens:
                logger.info(f"All tokens of {collection} saved")
                return 
            offset += 1
            token_models = self.get_tokens_models(tokens, collection)
            if token_models:
                Token.objects.bulk_create(token_models)

    def get_or_save_collection(self, collection):
        """ parse data and get or create collection by network and address """
        new_collection, created = Collection.objects.get_or_create(
            address=self.collection_address, 
            network=self.network,
        )
        if created:
            new_collection.name = collection.get('name')
            new_collection.description = collection.get('description')
            new_collection.symbol = collection.get('primary_asset_contracts')[0].get("symbol")
            new_collection.avatar_ipfs = collection.get('image_url')
            new_collection.standart = collection.get('primary_asset_contracts')[0].get("schema_name")
            new_collection.save()
        return new_collection, created


class CollectionImport:
    def __init__(self, collection, network, standart) -> None:
        self.collection = collection
        self.network = network
        self.standart = standart

    @property
    def contract_function(self):
        if self.standart=='ERC721':
            return self.network.get_erc721main_contract(self.collection).functions
        return self.network.get_erc1155main_contract(self.collection).functions

    def is_total_supply_valid(self) -> bool:
        # 1155 tokenURI - uri
        uri = 'tokenURI' if self.standart=='ERC721' else 'uri'
        try:
            getattr(self.contract_function, uri)(0).call()
            return True
        except ContractLogicError:
            return False

    @property
    def is_methods_valid(self) -> bool:
        attrs = [
            'symbol',
            'name',
            'baseURI',
            # 'contractURI',
            'balanceOf',
            # ownerOf

        ]
        if all([hasattr(self.contract_function, attr) for attr in attrs]):
            return True
        return False

    def is_valid(self) -> bool:
        if not self.is_total_supply_valid():
            return False, "Collection has't tokens"
        if not self.is_methods_valid:
            return False, "Collection methods is not valid"
        return True, ""

    def save_in_db(self):
        ...

    def get_name(self):
        return self.network.contract_call(
            method_type='read',
            contract_type=f'{self.standart.lower()}main',
            address=self.collection,
            function_name='name',
            input_params=(),
            input_type=(),
            output_types=('string',),
        ) 

    def get_symbol(self):
        return self.network.contract_call(
            method_type='read',
            contract_type=f'{self.standart.lower()}main',
            address=self.collection,
            function_name='symbol',
            input_params=(),
            input_type=(),
            output_types=('string',),
        ) 

    def save_in_db(self):
        ...

    # def save_in_db(self, request, avatar):
    #     collection = Collection()
    #     collection.name = self.get_name()
    #     collection.symbol = self.get_symbol()
    #     collection.address = self.collection
    #     collection.network = self.network
    #     collection.standart = self.standart
    #     self.avatar_ipfs = avatar
    #     self.description = request.data.get('description')
    #     self.short_url = request.data.get('short_url')
    #     self.creator = request.user
    #     self.save()


@dataclass(init=False)
class TokenData:
    token_id: int
    name: str
    image_url: str
    animation_url: str
    token_metadata: str
    description: str
    traits: dict
    owner: Optional[dict]
    creator: Optional[dict]
    asset_contract: dict

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)

    @property
    def details(self):
        return {trait.get('trait_type'): trait.get('value') for trait in self.traits}

    @property
    def owner_user(self):
        return self.get_user(self.owner)

    @property
    def creator_user(self):
        return self.get_user(self.creator)
    
    @property
    def format(self):
        return 'animation' if self.animation_url else 'image'
    
    @property
    def is_valid(self):
        return self.name and self.creator_user
    
    @property
    def creator_royalty(self):
        return self.asset_contract.get('dev_seller_fee_basis_points', 0) /100

    def get_user(self, user):
        if user and user.get('user'):
            try:
                adv_user = AdvUser.objects.get(username__iexact=user['address'])
            except AdvUser.DoesNotExist:
                adv_user = AdvUser.objects.create_user(
                    username=user['address'], 
                    display_name=user['user']['username'],
                    avatar_ipfs=user['profile_img_url'],
                )
            return adv_user

    def get_token_model(self, collection):
        return Token(
            name=self.name,
            internal_id=self.token_id,
            image=self.image_url,
            animation_file=self.animation_url,
            ipfs=self.token_metadata,
            details=self.details,
            format=self.format, 
            status=Status.PENDING,
            total_supply = 1,
            owner=self.owner_user,
            creator=self.creator_user,
            creator_royalty=self.creator_royalty,
            description=self.description,
            collection=collection,
        )

