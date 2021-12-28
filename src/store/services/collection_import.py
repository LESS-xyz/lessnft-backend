import logging
from dataclasses import dataclass, fields
from typing import Optional

import requests

from src.accounts.models import AdvUser
from src.settings import config
from src.store.models import Collection, Status, Token
from src.utilities import RedisClient

logger = logging.getLogger("celery")


class OpenSeaAPI:
    def asset_contract(self, collection_address):
        return requests.get(f"{config.OPENSEA_API}asset_contract/{collection_address}/")

    def collection(self, collection_slug):
        return requests.get(f"{config.OPENSEA_API}collection/{collection_slug}/")

    def assets(self, address, offset=0, limit=50):
        assert limit <= 50, "The max limit in api is 50"

        return requests.get(
            f"{config.OPENSEA_API}assets/",
            params={
                "asset_contract_address": address,
                "offset": offset,
                "limit": limit,
            },
        )


class OpenSeaImport:
    def __init__(self, collection_address, network):
        self.collection_address = collection_address
        self.network = network
        self.api = OpenSeaAPI()
        self.last_block = self.get_last_network_block()

    def _get_collection_slug(self):
        response = self.api.asset_contract(self.collection_address)
        if response.status_code == 200:
            return response.json()["collection"]["slug"]

    def get_collection_data(self):
        """Return collection data from opensea api"""
        slug = self._get_collection_slug()
        if not slug:
            return None
        response = self.api.collection(slug)
        if response.status_code == 200:
            return response.json().get("collection")
        return None

    def get_last_network_block(self):
        return self.network.get_last_block()

    def save_last_block(self, address):
        redis = RedisClient()
        key = f"mint_Ethereum_{address}_ERC721"
        redis.connection.set(key, self.last_block)

    def save_in_db(self, collection):
        """
        Parse collection data and create
        collection and tokens if not exists
        """
        collection_model, _ = self.get_or_save_collection(collection)
        self.save_tokens(collection_model)
        self.save_last_block(collection_model.address)
        collection_model.status = Status.COMMITTED
        collection_model.save()

    def _get_user(self, user):
        """
        Parse user data and get or create user by username
        """
        if not user["user"]:
            return None
        try:
            adv_user = AdvUser.objects.get(username__iexact=user["address"])
        except AdvUser.DoesNotExist:
            adv_user = AdvUser.objects.create_user(
                username=user["address"],
                display_name=user["user"]["username"],
                avatar_ipfs=user["profile_img_url"],
            )
        return adv_user

    def get_tokens_models(self, tokens, collection):
        """
        Check if token exists and valid
        and return list of Token instance
        """
        tokens = [TokenData(**token) for token in tokens]
        internal_ids = [token.token_id for token in tokens]
        internal_ids = list(
            Token.objects.filter(
                collection=collection,
                internal_id__in=internal_ids,
            ).values_list("internal_id", flat=True)
        )

        return [
            token.get_token_model(collection)
            for token in tokens
            if token.is_valid and token.token_id not in internal_ids
        ]

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
        """parse data and get or create collection by network and address"""
        new_collection, created = Collection.objects.get_or_create(
            address=self.collection_address,
            network=self.network,
        )
        if created:
            new_collection.name = collection.get("name")
            new_collection.description = collection.get("description")
            new_collection.symbol = collection.get("primary_asset_contracts")[0].get(
                "symbol"
            )
            new_collection.avatar_ipfs = collection.get("image_url")
            new_collection.cover_ipfs = collection.get("banner_image_url")
            new_collection.standart = collection.get("primary_asset_contracts")[0].get(
                "schema_name"
            )
            new_collection.deploy_block = self.network.get_last_block()
            new_collection.network = self.network
            new_collection.save()
        return new_collection, created


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
        return {trait.get("trait_type"): trait.get("value") for trait in self.traits}

    @property
    def owner_user(self):
        return self.get_user(self.owner)

    @property
    def creator_user(self):
        return self.get_user(self.creator)

    @property
    def format(self):
        return "animation" if self.animation_url else "image"

    @property
    def is_valid(self):
        return self.name and self.creator_user

    @property
    def creator_royalty(self):
        return self.asset_contract.get("dev_seller_fee_basis_points", 0) / 100

    def get_user(self, user):
        if user and user.get("user"):
            try:
                adv_user = AdvUser.objects.get(username__iexact=user["address"])
            except AdvUser.DoesNotExist:
                adv_user = AdvUser.objects.create_user(
                    username=user["address"],
                    display_name=user["user"]["username"],
                    avatar_ipfs=user["profile_img_url"],
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
            status=Status.COMMITTED,
            total_supply=1,
            owner=self.owner_user,
            creator=self.creator_user,
            creator_royalty=self.creator_royalty,
            description=self.description,
            collection=collection,
        )
