import random
import secrets
from typing import Tuple, Union
from decimal import *
from django.db import models
from web3 import Web3, HTTPProvider

from django.db.models import Q
from django.db.models.signals import post_save
from django.core.validators import MaxValueValidator, MinValueValidator
from dds.consts import MAX_AMOUNT_LEN
from dds.utilities import sign_message, get_media_from_ipfs
from dds.accounts.models import AdvUser
from dds.rates.models import UsdRate
from dds.consts import DECIMALS
from dds.settings import (
    NETWORK_SETTINGS,
    TOKEN_MINT_GAS_LIMIT,
    TOKEN_TRANSFER_GAS_LIMIT,
    TOKEN_BUY_GAS_LIMIT,
    ERC20_ADDRESS,
    DEFAULT_AVATARS,
    ERC721_FABRIC_ADDRESS,
    ERC1155_FABRIC_ADDRESS,
    EXCHANGE_ADDRESS
)
from contracts import (
    EXCHANGE,
    ERC721_MAIN,
    ERC1155_MAIN
)
from rest_framework import status
from rest_framework.response import Response
from rest_framework import status
from dds.consts import DECIMALS
from .services.ipfs import get_ipfs
from contracts import (
    ERC721_FABRIC,
    ERC1155_FABRIC,
)
from dds.settings import (
    SIGNER_ADDRESS,
    COLLECTION_CREATION_GAS_LIMIT,
)


class Status(models.TextChoices):
    PENDING = 'Pending'
    FAILED = 'Failed'
    COMMITTED = 'Committed'
    BURNED = 'Burned'


class Collection(models.Model):
    name = models.CharField(max_length=50, unique=True)
    avatar_ipfs = models.CharField(max_length=200, null=True, default=None)
    cover_ipfs = models.CharField(max_length=200, null=True, default=None)
    address = models.CharField(max_length=60, unique=True, null=True, blank=True)
    symbol = models.CharField(max_length=10, unique=True)
    description = models.TextField(null=True, blank=True)
    standart = models.CharField(max_length=10, choices=[('ERC721', 'ERC721'), ('ERC1155', 'ERC1155')])
    short_url = models.CharField(max_length=30, default=None, null=True, blank=True, unique=True)
    creator = models.ForeignKey('accounts.AdvUser', on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices)
    deploy_hash = models.CharField(max_length=100, null=True)
    deploy_block = models.IntegerField(null=True, default=None)

    @property
    def avatar(self):
        return get_media_from_ipfs(self.avatar_ipfs)

    @property
    def cover(self):
        return get_media_from_ipfs(self.cover_ipfs)

    @property
    def url(self):
        return self.short_url if self.short_url else self.id

    def __str__(self):
        return self.name

    def save_in_db(self, request, avatar):
        self.name = request.data.get('name')
        self.symbol = request.data.get('symbol')
        self.address = request.data.get('address')
        self.avatar_ipfs = avatar
        self.standart = request.data.get('standart')
        self.description = request.data.get('description')
        self.short_url = request.data.get('short_url')
        self.deploy_hash = request.data.get('tx_hash')
        self.creator = request.user
        self.save()


    def create_token(self, creator, ipfs, signature, amount):
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        if self.standart == 'ERC721':
            abi = ERC721_MAIN
        else:
            abi = ERC1155_MAIN
        myContract = web3.eth.contract(
            address=web3.toChecksumAddress(self.address),
            abi=abi)
        tx_params = {
            'chainId': web3.eth.chainId,
            'gas': TOKEN_MINT_GAS_LIMIT,
            'nonce': web3.eth.getTransactionCount(web3.toChecksumAddress(creator.username), 'pending'),
            'gasPrice': web3.eth.gasPrice,
        }
        if self.standart == 'ERC721':
            initial_tx = myContract.functions.mint( ipfs, signature).buildTransaction(tx_params)
        else:
            initial_tx = myContract.functions.mint( int(amount), ipfs, signature).buildTransaction(tx_params)
        return initial_tx

    @classmethod
    def collection_is_unique(cls, name, symbol, short_url) -> Tuple[bool, Union[Response, None]]:
        if Collection.objects.filter(name=name):
            return False, Response({'name': 'this collection name is occupied'}, status=status.HTTP_400_BAD_REQUEST)
        if Collection.objects.filter(symbol=symbol):
            return False, Response({'symbol': 'this collection symbol is occupied'}, status=status.HTTP_400_BAD_REQUEST)
        if short_url and Collection.objects.filter(short_url=short_url):
            return False, Response({'short_url': 'this collection short_url is occupied'}, status=status.HTTP_400_BAD_REQUEST)
        return True, None

    @classmethod
    def create_contract(cls, name, symbol, standart, owner):
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        baseURI = '/ipfs/'
        signature = sign_message(['address'], [SIGNER_ADDRESS])
        tx_params = {
            'chainId': web3.eth.chainId,
            'gas': COLLECTION_CREATION_GAS_LIMIT,
            'nonce': web3.eth.getTransactionCount(web3.toChecksumAddress(owner.username), 'pending'),
            'gasPrice': web3.eth.gasPrice,
        }
        if standart == 'ERC721':
            myContract = web3.eth.contract(
                address=web3.toChecksumAddress(ERC721_FABRIC_ADDRESS),
                abi=ERC721_FABRIC,
            )
            return myContract.functions.makeERC721(
                name, 
                symbol, 
                baseURI, 
                SIGNER_ADDRESS, 
                signature
            ).buildTransaction(tx_params)

        myContract = web3.eth.contract(
            address=web3.toChecksumAddress(ERC1155_FABRIC_ADDRESS),
            abi=ERC1155_FABRIC,
        )
        '''
        # JUST FOR TESTS
        tx = myContract.functions.makeERC1155(
            baseURI,
            SIGNER_ADDRESS,
            signature
        ).buildTransaction(tx_params)
        signed_tx = web3.eth.account.sign_transaction(tx,'92cf3cee409da87ce5eb2137f2befce69d4ebaab14f898a8211677d77f91e6b0')
        tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)
        return tx_hash.hex()
        '''
        return myContract.functions.makeERC1155(
            baseURI, 
            SIGNER_ADDRESS, 
            signature
        ).buildTransaction(tx_params)

    def get_contract(self):
        w3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        if self.standart == 'ERC1155':
            abi = ERC1155_MAIN
        else:
            abi = ERC721_MAIN
        contract = w3.eth.contract(
            address=Web3.toChecksumAddress(self.address),
            abi=abi
        )
        return contract


def collection_created_dispatcher(sender, instance, created, **kwargs):
    if created:
        instance.avatar_ipfs = random.choice(DEFAULT_AVATARS)
        instance.save()


post_save.connect(collection_created_dispatcher, sender=Collection)

def validate_nonzero(value):
    if value == 0:
        raise ValidationError(
            _('Quantity %(value)s is not allowed'),
            params={'value': value},
        )



class Token(models.Model):
    name = models.CharField(max_length=200, unique=True)
    tx_hash = models.CharField(max_length=200, null=True, blank=True)
    ipfs = models.CharField(max_length=200, null=True, default=None)
    standart = models.CharField(max_length=10, choices=[('ERC721', 'ERC721'), ('ERC1155', 'ERC1155')])
    total_supply = models.PositiveIntegerField(validators=[validate_nonzero])
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True,
                                null=True, validators=[MinValueValidator(Decimal('1000000000000000'))])
    minimal_bid = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True,
                                      null=True, validators=[MinValueValidator(Decimal('1000000000000000'))])
    currency = models.ForeignKey('rates.UsdRate', on_delete=models.PROTECT, null=True, default=None, blank=True)
    owner = models.ForeignKey('accounts.AdvUser', on_delete=models.PROTECT, related_name='%(class)s_owner', null=True, blank=True)
    owners = models.ManyToManyField('accounts.AdvUser', through='Ownership', null=True)
    creator = models.ForeignKey('accounts.AdvUser', on_delete=models.PROTECT, related_name='%(class)s_creator')
    creator_royalty = models.PositiveIntegerField(validators=[MaxValueValidator(99)])
    collection = models.ForeignKey('Collection', on_delete=models.CASCADE)
    internal_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    details = models.JSONField(blank=True, null=True, default=None)
    selling = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=Status.choices)
    updated_at = models.DateTimeField(auto_now_add=True)
    tags = models.ManyToManyField('Tags', blank=True, null=True)
    is_favorite = models.BooleanField(default=False)

    @property
    def media(self):
        return get_media_from_ipfs(self.ipfs)

    @property
    def is_selling(self):
        if self.standart == "ERC1155":
            return self.ownership_set.filter(
                selling=True, 
                price__isnull=False,
                currency__isnull=False,
            ).exists()
        return bool(self.selling and self.price and self.currency)

    @property
    def is_auc_selling(self):
        if self.standart == "ERC1155":
            return self.ownership_set.filter(
                selling=True, 
                price__isnull=True,
                currency__isnull=False,
            ).exists()
        return bool(self.selling and not self.price and self.currency)

    def __str__(self):
        return self.name

    def save_in_db(self, request, ipfs):
        self.name = request.data.get('name')
        self.standart = request.data.get('standart')
        self.status = Status.PENDING
        self.total_supply = request.data.get('total_supply')
        self.details = request.data.get('details')
        self.ipfs = ipfs
        self.description = request.data.get('description')
        self.creator_royalty = request.data.get('creator_royalty')
        price = request.data.get('price')
        creator = request.user
        collection = request.data.get('collection')
        selling = request.data.get('selling')
        self.creator = creator
        self.collection = Collection.objects.get(id=collection)
        collection_id = int(collection) if collection.isdigit() else None
        self.collection = Collection.objects.get(
            Q(id=collection_id) | Q(short_url=collection)
        )
        currency_symbol = request.data.get("currency")
        if currency_symbol:
            currency = UsdRate.objects.filter(symbol=currency_symbol).first()

        if self.standart == 'ERC721':
            self.currency = currency
            self.total_supply = 1
            self.owner = self.creator
            if selling == 'true':
                self.selling = True
            if request.data.get('minimal_bid'):
                self.minimal_bid = int(float(request.data.get('minimal_bid')) * self.currency.get_decimals)
            if price:
                self.price = int(float(price) * self.currency.get_decimals)
        else:
            self.full_clean()
            self.save()
            self.owners.add(creator)
            self.save()
            ownership = Ownership.objects.get(owner=creator, token=self)
            ownership.quantity = self.total_supply
            ownership.currency = currency
            if selling == 'true':
                ownership.selling = True
                self.selling=True
            if price:
                ownership.price = int(float(price) * self.currency.get_decimals)
            if self.price:
                if self.price > ownership.price:
                    self.price = ownership.price
                    self.full_clean()
                    self.save()
            else:
                self.price = ownership.price
                self.full_clean()
                self.save()
            minimal_bid = request.data.get('minimal_bid')
            if minimal_bid:
                minimal_bid = int(float(minimal_bid) * self.currency.get_decimals)
                ownership.minimal_bid = minimal_bid
                if self.minimal_bid:
                    if self.minimal_bid > minimal_bid:
                        self.minimal_bid = minimal_bid
                else:
                    self.minimal_bid = minimal_bid
                self.full_clean()
                self.save()
            ownership.full_clean()
            ownership.save()

        self.full_clean()
        self.save()

    def transfer(self, new_owner):
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        if self.standart == 'ERC721':
            abi = ERC721_MAIN
        else:
            abi = ERC1155_MAIN
        myContract = web3.eth.contract(
            address=web3.toChecksumAddress(self.collection.address),
            abi=abi)
        tx_params = {
            'chainId': web3.eth.chainId,
            'gas': TOKEN_TRANSFER_GAS_LIMIT,
            'nonce': web3.eth.getTransactionCount(web3.toChecksumAddress(self.owner.username), 'pending'),
            'gasPrice': web3.eth.gasPrice,
        }
        initial_tx = myContract.functions.transferFrom(web3.toChecksumAddress(self.owner.username),
                                        web3.toChecksumAddress(new_owner), self.internal_id).buildTransaction(tx_params)
        return initial_tx

    def buy_token(self, token_amount, buyer, master_account, seller=None, price=None):
        print(f'seller: {seller}')  

        id_order = '0x%s' % secrets.token_hex(32)

        if seller:
            seller_address = seller.username
        else:
            seller_address = self.owner.username
        if not price:
            if self.standart == 'ERC721':
                price = self.price
            else:
                price = Ownership.objects.get(token=self, owner=seller, selling=True).price

        types_list = [
            'bytes32', 
            'address', 
            'address', 
            'uint256', 
            'uint256',
            'address', 
            'uint256', 
            'address[]', 
            'uint256[]', 
            'address',
        ]

        values_list = [
            id_order,
            Web3.toChecksumAddress(seller_address),
            Web3.toChecksumAddress(self.collection.address),
            self.internal_id,
            token_amount,
            Web3.toChecksumAddress(self.currency.address),
            int(price),
            [
                Web3.toChecksumAddress(self.creator.username), 
                Web3.toChecksumAddress(master_account.address),
            ],
            [
                (int(self.creator_royalty / 100 * float(price))), 
                (int(master_account.commission / 100 * float(price))),
            ],
            Web3.toChecksumAddress(buyer.username)
        ]
        print(values_list)
        signature = sign_message(
            types_list,
            values_list
        )

        method = 'makeExchange{standart}'.format(standart=self.standart)

        data = {
            'idOrder': id_order,
            'SellerBuyer': [seller_address, buyer.username],
            'tokenToBuy': {
                'tokenAddress':self.collection.address,
                'id': self.internal_id,
                'amount': token_amount
            },
            'tokenToSell': {
                'tokenAddress': ERC20_ADDRESS,
                'id': 0,
                'amount': str(int(price))
            },
            'fee': {
                'feeAddresses': [self.creator.username, master_account.address],
                'feeAmounts': [
                    (int(self.creator_royalty / 100 * float(price))), 
                    (int(master_account.commission / 100 * float(price)))
                ]
            },
            'signature': signature
        }

        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))

        initial_tx = {
            'nonce': web3.eth.getTransactionCount(
                web3.toChecksumAddress(buyer.username), 'pending'
            ),
            'gasPrice': web3.eth.gasPrice,
            'gas': TOKEN_BUY_GAS_LIMIT,
            'to': EXCHANGE_ADDRESS,
            'method': method,
            'value': 0,
            'data': data
        }

        return Response({'initial_tx': initial_tx}, status=status.HTTP_200_OK)

    def get_owner_auction(self):
        owners_auction = self.ownership_set.filter(price=None, selling=True)

        owners_auction_info = []
        for owner in owners_auction:
            info = {
                'id': owner.owner.id,
                'name': owner.owner.display_name,
                'address': owner.owner.username,
                'avatar': owner.owner.avatar,
                'quantity': owner.quantity
            }
            owners_auction_info.append(info)
        return owners_auction_info


def token_save_dispatcher(sender, instance, created, **kwargs):
    if instance.standart == 'ERC1155':
        if not Ownership.objects.filter(token=instance).filter(selling=True):
            instance.selling = False
            instance.price = None
        else:
            instance.selling = True
            try:
                minimal_price = \
                Ownership.objects.filter(token=instance).filter(selling=True).exclude(price=None).order_by('price')[0].price
                for i in Ownership.objects.filter(token=instance).filter(selling=True).exclude(price=None).order_by('price'):
                    print(i.__dict__)
                print(minimal_price)
            except:
                minimal_price = None
            instance.price = minimal_price
        post_save.disconnect(token_save_dispatcher, sender=sender)
        instance.save(update_fields=['selling', 'price'])
        post_save.connect(token_save_dispatcher, sender=sender)

post_save.connect(token_save_dispatcher, sender=Token)


class Ownership(models.Model):
    token = models.ForeignKey('Token', on_delete=models.CASCADE)
    owner = models.ForeignKey('accounts.AdvUser', on_delete=models.CASCADE)
    currency = models.ForeignKey('rates.UsdRate', on_delete=models.PROTECT, null=True, default=None)
    quantity = models.PositiveIntegerField(null=True)
    selling = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True,
                                null=True, validators=[MinValueValidator(Decimal('1000000000000000'))])
    minimal_bid = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True,
                                null=True, validators=[MinValueValidator(Decimal('1000000000000000'))])

    @property
    def get_price(self):
        if self.price:
            return self.price
        return self.minimal_bid


class Tags(models.Model):
    name = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Tags"


class Bid(models.Model):
    token = models.ForeignKey('Token', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(null=True)
    user = models.ForeignKey('accounts.AdvUser', on_delete=models.PROTECT)
    amount = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN, 
        decimal_places=0, 
        default=None, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(Decimal('1000000000000000'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=50, choices=Status.choices, default=Status.PENDING)
