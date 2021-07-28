import decimal
import random
import uuid, secrets
from decimal import *
from collections import namedtuple
from typing import List
from django.db import models
from django.contrib.postgres.fields import ArrayField
from web3 import Web3, HTTPProvider
from eth_account import Account
from eth_abi import encode_single

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.dispatch import Signal
from django.core.validators import MaxValueValidator, MinValueValidator
from dds.consts import MAX_AMOUNT_LEN
from dds.utilities import get_timestamp_path, sign_message, get_media_if_exists
from dds.accounts.models import AdvUser
from dds.consts import DECIMALS
from dds.settings import (
    NETWORK_SETTINGS,
    TOKEN_MINT_GAS_LIMIT,
    TOKEN_TRANSFER_GAS_LIMIT,
    TOKEN_BUY_GAS_LIMIT,
    PRIV_KEY,
    ERC20_ADDRESS,
    DEFAULT_AVATARS
)
from contracts import (
    EXCHANGE,
    ERC721_FABRIC,
    ERC1155_FABRIC,
    ERC721_MAIN,
    ERC1155_MAIN,
    WETH_CONTRACT
)
from rest_framework import status
from rest_framework.authtoken.models import Token as AuthToken
from rest_framework.response import Response
from rest_framework import status
from dds.consts import DECIMALS
from .services.ipfs import get_ipfs


class Status(models.TextChoices):
    PENDING = 'Pending'
    FAILED = 'Failed'
    COMMITTED = 'Committed'
    BURNED = 'Burned'


class Collection(models.Model):
    name = models.CharField(max_length=50, unique=True)
    avatar = models.ImageField(blank=True, upload_to=get_timestamp_path)
    cover = models.ImageField(blank=True, upload_to=get_timestamp_path)
    address = models.CharField(max_length=60, unique=True, null=True, blank=True)
    symbol = models.CharField(max_length=10, unique=True)
    description = models.TextField(null=True, blank=True)
    standart = models.CharField(max_length=10, choices=[('ERC721', 'ERC721'), ('ERC1155', 'ERC1155')])
    short_url = models.CharField(max_length=30, default=None, null=True, blank=True, unique=True)
    creator = models.ForeignKey('accounts.AdvUser', on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices)
    deploy_hash = models.CharField(max_length=100, null=True)
    deploy_block = models.IntegerField(null=True, default=None)

    def __str__(self):
        return self.name

    def save_in_db(self, request):
        self.name = request.data.get('name')
        try:
            self.avatar = request.FILES.get('filename')
        except:
            pass
        self.symbol = request.data.get('symbol')
        self.address = request.data.get('address')
        self.standart = request.data.get('standart')
        self.description = request.data.get('description')
        self.short_url = request.data.get('short_url')
        self.deploy_hash = request.data.get('tx_hash')
        creator = request.data.get('creator')
        token = AuthToken.objects.get(key=creator)
        self.creator = AdvUser.objects.get(id=token.user_id)
        self.save()
        try:
            self.avatar.save(request.FILES.get('avatar').name, request.FILES.get('avatar'))
        except:
            pass

    def create_token(self, creator, ipfs, signature, amount):
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        if self.standart == 'ERC721':
            abi = ERC721_MAIN['abi']
        else:
            abi = ERC1155_MAIN['abi']
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

def collection_created_dispatcher(sender, instance, created, **kwargs):
    if created:
        instance.avatar = random.choice(DEFAULT_AVATARS)
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
    tx_hash = models.CharField(max_length=200, default='0xE4Bdc4D423FaC9549bdCcabD1b59071E4fe99BDa')
    ipfs = models.CharField(max_length=200, null=True, default=True)
    standart = models.CharField(max_length=10, choices=[('ERC721', 'ERC721'), ('ERC1155', 'ERC1155')])
    total_supply = models.PositiveIntegerField(validators=[validate_nonzero])
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True,
                                null=True, validators=[MinValueValidator(Decimal('1000000000000000'))])
    minimal_bid = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True,
                                      null=True, validators=[MinValueValidator(Decimal('1000000000000000'))])
    currency = models.CharField(max_length=20, default='ETH')
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

    @property
    def media(self):
        if not self.ipfs:
            return None
        return "https://ipfs.io/ipfs/{ipfs}".format(ipfs=self.ipfs)

    def __str__(self):
        return self.name

    def save_in_db(self, request):
        self.name = request.data.get('name')
        self.standart = request.data.get('standart')
        self.status = Status.COMMITTED
        self.total_supply = request.data.get('total_supply')
        self.currency = request.data.get('currency')
        self.tx_hash = request.data.get('tx_hash')
        self.details = request.data.get('details')
        self.description = request.data.get('description')
        self.creator_royalty = request.data.get('creator_royalty')
        price = request.data.get('price')
        creator = request.data.get('creator')
        token = AuthToken.objects.get(key=creator)
        creator = AdvUser.objects.get(id=token.user_id)
        collection = request.data.get('collection')
        selling = request.data.get('selling')
        self.creator = creator
        self.collection = Collection.objects.get(id=collection)

        if self.standart == 'ERC721':
            self.total_supply = 1
            self.owner = self.creator
            if selling == 'true':
                self.selling = True
            if request.data.get('minimal_bid'):
                self.minimal_bid = int(float(request.data.get('minimal_bid')) * DECIMALS[self.currency])
            if price:
                self.price = int(float(price) * DECIMALS[self.currency])
        else:
            self.full_clean()
            self.save()
            self.owners.add(creator)
            self.save()
            ownership = Ownership.objects.get(owner=creator, token=self)
            ownership.quantity = self.total_supply
            if selling == 'true':
                ownership.selling = True
                self.selling=True
            if price:
                ownership.price = int(float(price) * DECIMALS[self.currency])
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
                minimal_bid = int(float(minimal_bid) * DECIMALS[self.currency])
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
        ipfs = get_ipfs(self)
        if ipfs:
            self.ipfs = ipfs["media"] 
        self.save()

    def transfer(self, new_owner):
        web3 = Web3(HTTPProvider(NETWORK_SETTINGS['ETH']['endpoint']))
        if self.standart == 'ERC721':
            abi = ERC721_MAIN['abi']
        else:
            abi = ERC1155_MAIN['abi']
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

        types_list = [
            'bytes32', 'address', 'address', 'uint256', 'uint256',
            'address', 'uint256', 'address[]', 'uint256[]', 'address'
        ]

        if seller:
            seller_address = seller.username
        else:
            seller_address = self.owner.username
        if not price:
            if self.standart == 'ERC721':
                price = self.price
            else:
                price = Ownership.objects.get(token=self, owner=seller, selling=True).price

        values_list = [
            id_order,
            Web3.toChecksumAddress(seller_address),
            Web3.toChecksumAddress(self.collection.address),
            self.internal_id,
            token_amount,
            Web3.toChecksumAddress(ERC20_ADDRESS),
            int(price),
            [Web3.toChecksumAddress(self.creator.username), Web3.toChecksumAddress(master_account.address)],
            [(int(self.creator_royalty / 100 * float(price))), 
            (int(master_account.commission / 100 * float(price)))],
            Web3.toChecksumAddress(buyer.username)
        ]
        print(values_list)
        signature = sign_message(
            types_list,
            values_list
        )

        method = 'makeExchangeERC721'
        if self.standart == 'ERC1155':
            method = 'makeExchangeERC1155'

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
            'to': EXCHANGE['address'],
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
                'avatar': get_media_if_exists(owner.owner, 'avatar'),
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
    quantity = models.PositiveIntegerField(null=True)
    selling = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True,
                                null=True, validators=[MinValueValidator(Decimal('1000000000000000'))])
    minimal_bid = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=0, default=None, blank=True,
                                null=True, validators=[MinValueValidator(Decimal('1000000000000000'))])


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
