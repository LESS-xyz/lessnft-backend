import requests
import logging
from web3.exceptions import ContractLogicError
from src.store.models import Collection, Token, Status
from src.accounts.models import AdvUser


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

    def create_token(self, token, collection):
        """
        Parse token data and return Token instance
        """
        if not token.get('creator'):
            return None
        standart = token.get('asset_contract').get('schema_name')
        traits = token.get('traits')
        details = {trait.get('trait_type'): trait.get('value') for trait in traits}
        return Token(
            name=token.get('name'),
            internal_id=token.get('token_id'),
            image=token.get('image_url'),
            animation_file=token.get('animation_url'),
            ipfs=token.get('token_metadata'),
            details=details,
            format='animation' if token.get('animation_url') else 'image', 
            status=Status.PENDING,
            total_supply = 1, # TODO: refactor hardcode
            owner=self._get_user(token.get('owner')),
            # owners = ???
            creator=self._get_user(token.get('creator')),
            creator_royalty=token['asset_contract'].get('dev_seller_fee_basis_points', 0) /100,
            description=token.get("description"),
            collection=collection,
        )

    def get_valid_tokens(self, tokens, collection):
        """
        Return list of tokens without exists or
        invalid tokens (token hasn't name)
        """
        internal_ids =  [t.get("token_id") for t in tokens]
        internal_ids = list(Token.objects.filter(
            collection=collection, 
            internal_id__in=internal_ids,
        ).values_list("internal_id", flat=True))

        is_valid = lambda token: int(token.get("token_id")) not in internal_ids and token.get('name')

        return [token for token in tokens if is_valid(token)]

    def get_tokens_models(self, tokens, collection):
        """
        Check if token exists and valid
        and return list of Token instance
        """
        tokens = self.get_valid_tokens(tokens, collection)
        token_models = [self.create_token(token, collection) for token in tokens]
        return [token for token in token_models if token]
    
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