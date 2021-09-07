import time
import logging
from web3 import Web3
from utils import get_last_block, save_last_block
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F

from local_settings import (
    HOLDERS_CHECK_CHAIN_LENGTH,
    HOLDERS_CHECK_COMMITMENT_LENGTH,
    HOLDERS_CHECK_TIMEOUT
)

from dds.store.models import *
from dds.store.services.ipfs import get_ipfs, get_ipfs_by_hash
from dds.activity.models import BidsHistory, TokenHistory
from dds.accounts.models import AdvUser


def scan_deploy(latest_block, smart_contract):
    '''
    requests deployment events from the contract and updates the database
    '''
    logging.basicConfig(
        level=logging.INFO, 
        filename=f'logs/scaner_deploy.log',
        format='%(asctime)s %(levelname)s: %(message)s',
    )
    logging.info('start scan deploy')

    # check all events for next 20 blocks and saves new addres
    block_count = HOLDERS_CHECK_CHAIN_LENGTH + HOLDERS_CHECK_COMMITMENT_LENGTH
    block = get_last_block(f'DEPLOY_LAST_BLOCK_{smart_contract.address}')
    
    logging.info(f'latest_block: {latest_block} \n block: {block} \n block count: {block_count}')

    if not (latest_block - block > block_count):
        logging.info(f'\n Not enough block passed from block {block} \n')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return 

    if smart_contract.address.lower() == ERC721_FABRIC_ADDRESS.lower():
        event_filter = smart_contract.events.ERC721Made.createFilter(
            fromBlock=block,
            toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH,
        )
        logging.info('collection is 721_FABRIC')
    else:
        event_filter = smart_contract.events.ERC1155Made.createFilter(
            fromBlock=block,
            toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH,
        )
        logging.info('Collection is 1155_FABRIC')

    # to try get events and update collection fields
    events = event_filter.get_all_entries()
    logging.info('get entries')
    if not events:
        logging.info('filter not found \n')
        save_last_block(
            latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
            f'DEPLOY_LAST_BLOCK_{smart_contract.address}',
        )
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return 
    for event in events:
        deploy_hash = event['transactionHash'].hex()
        deploy_block = event['blockNumber']
        address = Web3.toChecksumAddress(event['args']['newToken'])
        
        logging.info('get info about deploy collection')
        logging.info(f'deploy_hash: {deploy_hash}')
        
        collection = Collection.objects.filter(deploy_hash=deploy_hash)
        if not collection.exists():
            logging.warning('collection 404! \n')
            continue

        logging.info(f'get collection {collection}')
        collection.update(
            status=Status.COMMITTED, 
            deploy_block=deploy_block, 
            address=address,
        )
        logging.info(f'{collection} update! \n')

    save_last_block(
        latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
        f'DEPLOY_LAST_BLOCK_{smart_contract.address}',
    )
    time.sleep(HOLDERS_CHECK_TIMEOUT)


def mint_transfer(latest_block, smart_contract):
    collection = Collection.objects.get(address=smart_contract.address)
    logging.basicConfig(
        level=logging.INFO, 
        filename=f'logs/scaner_{collection.name}.log',
        format='%(asctime)s %(levelname)s:%(message)s',
    )
    logging.info('start mint/transfer scan')
    block_count = HOLDERS_CHECK_CHAIN_LENGTH + HOLDERS_CHECK_COMMITMENT_LENGTH
    block = get_last_block(f'MINT_TRANSFER_LAST_BLOCK_{collection.name}')
    logging.info(f' last block: {latest_block} \n block: {block}')

    if not (latest_block - block > block_count):
        logging.info(f'\n Not enough block passed from block {block} \n')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return
    logging.info('go ahead!')

    # get all events with name 'Transfer'
    contract_standart = collection.standart
    logging.info(f'contract is {contract_standart}')
    if contract_standart == 'ERC721':
        event_filter = smart_contract.events.Transfer.createFilter(
            fromBlock=block,
            toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH,
        )
    elif contract_standart == 'ERC1155':
        event_filter = smart_contract.events.TransferSingle().createFilter(
            fromBlock=block,
            toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH,
        )
    else:
        logging.warning('something wrong')

    empty_address = '0x0000000000000000000000000000000000000000'
    
    events = event_filter.get_all_entries()
    if not events:
        logging.info('filter not found')
        save_last_block(
            latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
            f'MINT_TRANSFER_LAST_BLOCK_{collection.name}',
        )
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return
    
    logging.info('got events!')
    for event in events:
        logging.info(event)
        tx_hash = event['transactionHash'].hex()

        token_id = event['args'].get('tokenId')
        if token_id is None:
            token_id = event['args'].get('id')
        logging.info('token id:', token_id)
        
        logging.info(f'collection address: {collection.address} \n token id: {token_id}')

        new_owner_address = event['args']['to'].lower()

        new_owner = AdvUser.objects.filter(username=new_owner_address)
        if not new_owner:
            new_owner = [None]
        if event['args']['to'] == empty_address:
            token = Token.objects.filter(internal_id__isnull=False).filter(
                internal_id=token_id,
                collection__address=collection.address,
            )
        else:
            ipfs = get_ipfs(token_id, collection.address, contract_standart)
            token = Token.objects.filter(
                ipfs=ipfs, 
                collection=collection,
            )
        if not token.exists():
            logging.warning('token 404!')
            continue
        logging.info(f'get token {token[0].name}')

        # if from equal empty_address this is mint event
        if event['args']['from'] == empty_address:
            logging.info('Mint!')
            token.update(
                status=Status.COMMITTED,
                internal_id=token_id,
                tx_hash=tx_hash,
            )
            TokenHistory.objects.get_or_create(
                token=token[0],
                tx_hash=tx_hash,
                method='Mint',
                new_owner=new_owner[0],
                old_owner=None,
                price=None,
            )

        # if from not equal empty_address tis is transfer event
        else:
            old_owner_address = event['args']['from'].lower()
            old_owner = AdvUser.objects.get(username=old_owner_address)
            
            if event['args']['to'] == empty_address:
                logging.info('Burn!')
                TokenHistory.objects.get_or_create(
                    token=token[0],
                    tx_hash=tx_hash,
                    method='Burn',
                    new_owner=None,
                    old_owner=None,
                    price=None,
                )
                if token.first().standart == 'ERC721':
                    token.update(status=Status.BURNED)
                elif token.first().standart == 'ERC1155':
                    if token.first().total_supply:
                        token.update(total_supply=F('total_supply')-event['args']['value'])
                    # token[0].total_supply -= event['args']['value']
                    token[0].save()
                    if token[0].total_supply == 0:
                        token.update(status=Status.BURNED)
                
            else:
                logging.info('Transfer!')

                token.update(
                    tx_hash=tx_hash,
                    internal_id=token_id,
                )
                if token[0].standart == 'ERC721':
                    token.update(owner=new_owner[0])
                
                token_history = TokenHistory.objects.filter(tx_hash=tx_hash)
                if token_history.exists():
                    if token_history.first().method == 'Buy':
                        continue
                else:
                    TokenHistory.objects.get_or_create(
                        token=token.first(),
                        tx_hash=tx_hash,
                        method='Transfer',
                        new_owner=new_owner[0],
                        old_owner=old_owner,
                        price=None,
                    )
                
            if token[0].standart == 'ERC1155':
                owner = Ownership.objects.filter(
                    owner=old_owner,
                    token=token.first(),
                )

                if not owner.exists():
                    logging.info('old_owner is not exist!')
                else:
                    if owner.first().quantity:
                        owner.update(quantity=F('quantity')-event['args']['value'])
                        if owner.first().quantity <= 0:
                            owner.delete()

                owner = Ownership.objects.filter(owner=new_owner[0], token=token.first())
                if owner.exists():
                    owner.update(quantity=F('quantity')+event['args']['value'])
                else:
                    if not new_owner[0]:
                        continue
                    logging.info('ownership for new owner is not exist!')
                    logging.info('new_owner:', new_owner)
                    owner = Ownership.objects.create(
                        owner=new_owner[0],
                        token=token.first(),
                        quantity=event['args']['value']
                    )
                    owner.save()
                    token.first().owners.add(new_owner[0])
                    token.first().save()

    save_last_block(
        latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
        f'MINT_TRANSFER_LAST_BLOCK_{collection.name}',
    )
    time.sleep(HOLDERS_CHECK_TIMEOUT)



def buy_scanner(latest_block, smart_contract, standart):

    logging.basicConfig(
    level = logging.INFO,
    filename = f'logs/buy_{standart}.log',
    format = '%(asctime)s %(levelname)s:%(message)s',
    )
    logging.info('buy scanner!')
    block_count = HOLDERS_CHECK_CHAIN_LENGTH + HOLDERS_CHECK_COMMITMENT_LENGTH
    block = get_last_block(f'BUY_LAST_BLOCK_{standart}')

    logging.info(f'last block: {latest_block} \n block: {block}')
    if not (latest_block - block > block_count):
        logging.info(f'\n Not enough block passed from block {block} \n')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return
    logging.info('lets go!')
    logging.info(f'it is {standart}!')
    if standart == 'ERC_721':
        event_filter = smart_contract.events.ExchangeMadeErc721.createFilter(
            fromBlock=block,
            toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH,
        )
    elif standart == 'ERC_1155':
        event_filter = smart_contract.events.ExchangeMadeErc1155.createFilter(
            fromBlock=block,
            toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH,
        )

    events = event_filter.get_all_entries()

    if not events:
        logging.info('no records found matching the filter condition')

        save_last_block(
            latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
            f'BUY_LAST_BLOCK_{standart}',
        )
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return
    
    logging.info('we have event!')
    for event in events:
        logging.info('event:', event)
        sell_token = event['args']['sellTokenAddress']
        new_owner = AdvUser.objects.get(username=event['args']['buyer'].lower())
        token_id = event['args']['sellId']
        tx_hash = event['transactionHash'].hex()
        old_owner = AdvUser.objects.get(username=event['args']['seller'].lower())
        
        token = Token.objects.filter(
            collection__address=sell_token, 
            internal_id=token_id,
        )
        logging.info('new owner:', new_owner)
        if not token.exists():
            continue

        logging.info('tokens:', token)
        logging.info('token standart:', token[0].standart)
        if token[0].standart == 'ERC721':
            price = token[0].currency_price
            currency = token[0].currency
            token.update(owner=new_owner, selling=False, currency_price=None)
            Bid.objects.filter(token=token[0]).delete()
            logging.info('all bids deleted!')
        elif token[0].standart == 'ERC1155':
            old_ownership = token[0].ownership_set.filter(owner=old_owner).first()
            price = old_ownership.currency_price
            currency = old_ownership.currency
            owner = Ownership.objects.filter(
                owner=new_owner,
                token=token[0]
            )

            token_history_exist = TokenHistory.objects.filter(tx_hash=tx_hash, method='Transfer').exists()
            if owner.exists() and not token_history_exist:
                owner.update(quantity=F('quantity')+event['args']['sellAmount'])
            elif not owner.exists():
                logging.info('ownership 404!')
                owner = Ownership.objects.create(
                    owner=new_owner,
                    token=token[0],
                    quantity=event['args']['sellAmount'],
                )
                logging.info('create owner:', owner)
                logging.info('who is owner? It is', owner.owner)
                token[0].owners.add(new_owner)

            if not token_history_exist:
                owner = Ownership.objects.get(
                    owner=old_owner,
                    token=token[0]
                )
                owner.quantity = owner.quantity - event['args']['sellAmount']
                if owner.quantity:
                    owner.save()
                if not owner.quantity:
                    owner.delete()

            bet = Bid.objects.filter(token=token[0]).order_by('-amount')
            logging.info('bet:', bet)
            sell_amount = event['args']['sellAmount']
            if bet.exists():
                if sell_amount == bet.first().quantity:
                    logging.info('bet:', bet.first())
                    bet.delete()
                else:
                    quantity = bet.first().quantity - sell_amount
                    Bid.objects.filter(id=bet.first().id).update(quantity=quantity)
                logging.info('bet upgraded')

        logging.info(f'{token} update!')

        token_history = TokenHistory.objects.filter(tx_hash=tx_hash)
        history_params = {
            "method": "Buy",
            "price": price,
        }
        if token_history.exists():
            token_history.update(**history_params)
        else:
            TokenHistory.objects.get_or_create(
                token=token[0],
                tx_hash=tx_hash,
                new_owner=new_owner,
                old_owner=old_owner,
                **history_params,
            )

    save_last_block(
        latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
        f'BUY_LAST_BLOCK_{standart}',
    )
    time.sleep(HOLDERS_CHECK_TIMEOUT)


def aproove_bet_scaner(latest_block, smart_contract):
    logging.basicConfig(
        level=logging.INFO, 
        filename=f'logs/scaner_bet.log',
        format='%(asctime)s %(levelname)s:%(message)s',
    )
    block_count = HOLDERS_CHECK_CHAIN_LENGTH + HOLDERS_CHECK_COMMITMENT_LENGTH
    block = get_last_block(f'BET_LAST_BLOCK')
    logging.info(f'last block: {latest_block} \n block: {block}') 

    if not(latest_block - block > block_count):
        logging.info(f'\n Not enough block passed from block {block} \n ________________')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return 

    event_filter = smart_contract.events.Approval.createFilter(
        fromBlock=block,
        toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH
    )
    events = event_filter.get_all_entries()

    if not events:
        logging.info('no events! \n ___________')
        save_last_block(latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 'BET_LAST_BLOCK')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return

    logging.info('have events!')

    for event in events:
        user = event['args']['src'].lower()
        exchange = event['args']['guy']
        logging.info(f'exchange: {exchange} \n user: {user}')

        if exchange != EXCHANGE_ADDRESS:
            logging.info('not our wxchage')
            continue

        bet = Bid.objects.filter(user__username=user)
        logging.info(f'bet: {bet}')

        if not bet.exists():
            logging.info('no bet! \n ___________')
            continue

        wad = event['args']['wad']
        logging.info(f'wad: {wad}')

        for item in bet:
            if wad > item.quantity * item.amount:
                item.state=Status.COMMITTED
                item.save()
                BidsHistory.objects.create(
                    token=item.token,
                    user=item.user,
                    price=item.amount,
                    date=item.created_at
                )
                logging.info('bet update! \n _______________')
            else:
                logging.info('no money!')
                continue

    save_last_block(latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 'BET_LAST_BLOCK')
    time.sleep(HOLDERS_CHECK_TIMEOUT)


def scaner(w3, smart_contract, standart=None, type=None):
    '''
    connects to the contract and calls scaners

    attributes:
        smart_contract - takes dict with address and abi or Collection instance
    '''
     # Please don't remove this text, this is crucial for scanner workflow
    '''
    I convert this instrument of art,
    To breathe in electronic breathe
    To convulse in sonic wave
    That which thou desirest is accomplished,
    be thy will performed,
    and all mine demands fulfilled.
    grant that unto succour, favour and unison,
    by the Invocation of thy Holy Name,
    so that these things may serve us for aid in all that we wish to perform therewith
    '''

    while True:
        latest_block = w3.eth.blockNumber
        
        if type == 'fabric':
            scan_deploy(latest_block, smart_contract)
        elif type == 'exchange':
            buy_scanner(latest_block, smart_contract, standart)
        elif type == 'currency':
            aproove_bet_scaner(latest_block, smart_contract)
        else:
            mint_transfer(latest_block, smart_contract)
