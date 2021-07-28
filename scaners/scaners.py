import time
import logging
from web3 import Web3, HTTPProvider
from utils import get_last_block, save_last_block
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F
from contracts import (
    EXCHANGE,
    ERC721_FABRIC,
    ERC1155_FABRIC,
    ERC721_MAIN,
    ERC1155_MAIN,
    WETH_CONTRACT
)

from local_settings import (
                        HOLDERS_CHECK_CHAIN_LENGTH,
                        HOLDERS_CHECK_COMMITMENT_LENGTH,
                        HOLDERS_CHECK_TIMEOUT
                    )

from dds.store.models import *
from dds.activity.models import BidsHistory, TokenHistory
from dds.accounts.models import AdvUser


def scan_deploy(latest_block, dds_contract, smart_contract):
    '''
    requests deployment events from the contract and updates the database
    '''
    logging.basicConfig(level=logging.INFO, filename=f'logs/scaner_deploy.log',
                    format='%(asctime)s %(levelname)s: %(message)s')
    logging.info('start scan deploy')

    # check all events for next 20 blocks and saves new addres
    block_count = HOLDERS_CHECK_CHAIN_LENGTH + HOLDERS_CHECK_COMMITMENT_LENGTH
    block = get_last_block(f'DEPLOY_LAST_BLOCK_{smart_contract["address"]}')
    
    logging.info(f'latest_block: {latest_block} \n block: {block} \n block count: {block_count}')

    if latest_block - block > block_count:
        if smart_contract == ERC721_FABRIC:
            event_filter = dds_contract.events.ERC721Made.createFilter(
                                fromBlock=block,
                                toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH
                            )

            logging.info('collection is 721_FABRIC')

        else:
            event_filter = dds_contract.events.ERC1155Made.createFilter(
                                fromBlock=block,
                                toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH
                            )
            
            logging.info('Collection is 1155_FABRIC')

        # to try get events and update collection fields
        events = event_filter.get_all_entries()
        logging.info('get entries')
        if events != []:
            for event in events:
                deploy_hash = event['transactionHash'].hex()
                deploy_block = event['blockNumber']
                address = Web3.toChecksumAddress(event['args']['newToken'])
                
                logging.info('get info about deploy collection')
                logging.info(f'deploy_hash: {deploy_hash}')
                
                collection = Collection.objects.filter(deploy_hash=deploy_hash)
                if collection.exists():
                    logging.info(f'get collection {collection}')
                else:
                    logging.warning('collection 404! \n')
                    continue
                
                collection.update(status=Status.COMMITTED, deploy_block=deploy_block, address=address)
                
                logging.info(f'{collection} update! \n')

        else:
            logging.info('filter not found \n')

        save_last_block(latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, f'DEPLOY_LAST_BLOCK_{smart_contract["address"]}')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        
    else:
        logging.info(f'\n Not enough block passed from block {block} \n')
        time.sleep(HOLDERS_CHECK_TIMEOUT)


def mint_transfer(latest_block, dds_contract, smart_contract):

    logging.basicConfig(level=logging.INFO, filename=f'logs/scaner_{smart_contract.name}.log',
                    format='%(asctime)s %(levelname)s:%(message)s')
    logging.info('start mint/transfer scan')
    block_count = HOLDERS_CHECK_CHAIN_LENGTH + HOLDERS_CHECK_COMMITMENT_LENGTH
    block = get_last_block(f'MINT_TRANSFER_LAST_BLOCK_{smart_contract.name}')
    logging.info(f' last block: {latest_block} \n block: {block}')

    if latest_block - block > block_count:
        logging.info('go ahead!')
        # get all events with name 'Transfer'
        contract_standart = smart_contract.standart
        if contract_standart == 'ERC721':
            event_filter = dds_contract.events.Transfer.createFilter(
                                fromBlock=block,
                                toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH
                            )
            logging.info('contract is 721')
        elif contract_standart == 'ERC1155':
            event_filter = dds_contract.events.TransferSingle().createFilter(
                                fromBlock=block,
                                toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH
                            )
            logging.info('contract is 1155')
        else:
            logging.warning('something wrong')
    else:
        logging.info(f'\n Not enough block passed from block {block} \n')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return

    empty_address = '0x0000000000000000000000000000000000000000'
    
    events = event_filter.get_all_entries()
    if not events:
        logging.info('filter not found')
        save_last_block(latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
            f'MINT_TRANSFER_LAST_BLOCK_{smart_contract.name}')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return
    
    logging.info('got events!')
    for event in events:
        print(event)
        tx_hash = event['transactionHash'].hex()

        token_id = event['args'].get('tokenId')
        if not token_id:
            token_id = event['args'].get('id')
        print('token id:', token_id)
        
        coll_addr = event['address']
        logging.info(f'collection address: {coll_addr} \n token id: {token_id}')

        new_owner_address = event['args']['to'].lower()

        new_owner = AdvUser.objects.filter(username=new_owner_address)
        if not new_owner.exists():
            new_owner = [None]
        
        # if from equal empty_address this is mint event
        if event['args']['from'] == empty_address:
            token = Token.objects.filter(
                    tx_hash=tx_hash, 
                    collection__address=coll_addr
                )
            if token.exists():
                logging.info(f'get token {token[0].name}')
            else:
                logging.warning('token 404!')
                continue
            
            logging.info('Mint!')
            
            token.update(status=Status.COMMITTED, internal_id=token_id)
            TokenHistory.objects.get_or_create(
                token = token[0],
                tx_hash=tx_hash,
                method='Mint',
                new_owner=new_owner[0],
                old_owner=None,
                price=None
            )
        # if from not equal empty_address tis is transfer event
        elif event['args']['from'] != empty_address:

            token = Token.objects.filter(
                    internal_id=token_id, 
                    collection__address=coll_addr
                )
            if token.exists():
                logging.info(f'get token {token[0].name}')
            else:
                logging.warning('token 404!')
                continue
            
            old_owner_address = event['args']['from'].lower()
            old_owner = AdvUser.objects.get(username=old_owner_address)
            
            if event['args']['to'] == empty_address:
                logging.info('Burn!')
                TokenHistory.objects.get_or_create(
                    token = token[0],
                    tx_hash=tx_hash,
                    method='Burn',
                    new_owner=None,
                    old_owner=None,
                    price=None
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
                
                    
            if event['args']['to'] != empty_address:
                logging.info('Transfer!')

                token.update(owner=new_owner[0])
                
                wtf = TokenHistory.objects.filter(tx_hash=tx_hash)
                if wtf.exists():
                    if wtf.first().method == 'Buy':
                        continue
                if not wtf.exists():
                    TokenHistory.objects.get_or_create(
                        token = token.first(),
                        tx_hash=tx_hash,
                        method='Transfer',
                        new_owner=new_owner[0],
                        old_owner=old_owner,
                        price=None
                    )
                
            if token[0].standart == 'ERC1155':
                owner = Ownership.objects.filter(
                        owner=old_owner,
                        token=token.first()
                    )
                if not owner.exists():
                    print('old_owner is not exist!')
               
                else:
                    if owner.first().quantity:
                        owner.update(quantity = F('quantity')-event['args']['value'])
                    if not owner.first().quantity:
                        owner.delete()

                owner = Ownership.objects.filter(owner=new_owner[0], token=token.first())
                if owner.exists():
                    owner.update(quantity = F('quantity')+event['args']['value'])
                else:
                    if not new_owner[0]:
                        continue
                    print('ownership for new owner is not exist!')
                    print('new_owner:', new_owner)
                    owner = Ownership.objects.create(
                        owner=new_owner[0],
                        token=token.first(),
                        quantity=event['args']['value']
                    )
                    token.first().owners.add(owner)
                
                owner.save()
                
        else:
            logging.info('event with strange from address')


    save_last_block(latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, f'MINT_TRANSFER_LAST_BLOCK_{smart_contract.name}')
    time.sleep(HOLDERS_CHECK_TIMEOUT)



def buy_scanner(latest_block, dds_contract, standart):
    print('buy scanner!') 
    block_count = HOLDERS_CHECK_CHAIN_LENGTH + HOLDERS_CHECK_COMMITMENT_LENGTH
    block = get_last_block(f'BUY_LAST_BLOCK_{standart}')

    print(f'last block: {latest_block} \n block: {block}')
    if latest_block - block > block_count:
        print('lets go!')
        if standart == 'ERC_721':
            print('it is 721!')
            event_filter = dds_contract.events.ExchangeMadeErc721.createFilter(
                                fromBlock=block,
                                toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH
                            )
        elif standart == 'ERC_1155':
            print('it is 1155')
            event_filter = dds_contract.events.ExchangeMadeErc1155.createFilter(
                                fromBlock=block,
                                toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH
                            )
    else:
        print(f'\n Not enough block passed from block {block} \n')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return

    events = event_filter.get_all_entries()

    if not events:
        print('no records found matching the filter condition')

        save_last_block(latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
            f'BUY_LAST_BLOCK_{standart}')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        return
    
    print('we have event!')
    for event in events:
        print('event:', event)
        sell_token = event['args']['sellTokenAddress']
        new_owner = AdvUser.objects.get(username=event['args']['buyer'].lower())
        token_id = event['args']['sellId']
        tx_hash = event['transactionHash'].hex()
        old_owner = AdvUser.objects.get(username=event['args']['seller'].lower())
        
        token = Token.objects.filter(collection__address=sell_token, 
            internal_id=token_id)
        print('new owner:', new_owner)
        if not token.exists():
            continue

        print('tokens:', token)
        print('token standart:', token[0].standart)
        if token[0].standart == 'ERC721':
            print('in ERC 721')
            token.update(owner=new_owner, selling=False, price=None)
            Bid.objects.filter(token=token[0]).delete()
            print('all bids deleted!')
        elif token[0].standart == 'ERC1155':
            print('in erc 1155')
            owner = Ownership.objects.filter(
                    owner=new_owner,
                    token=token[0]
                )

            token_history_exist = TokenHistory.objects.filter(tx_hash=tx_hash, method='Transfer').exists()
            if owner.exists() and not token_history_exist:
                owner.update(quantity=F('quantity')+event['args']['sellAmount'])
            elif not owner.exists():
                print('ownership 404!')
                owner = Ownership.objects.create(
                    owner=new_owner,
                    token=token[0],
                    quantity=event['args']['sellAmount'],
                )
                print('create owner:', owner)
                print('who is owner? It is', owner.owner)
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
            print('bet:', bet)
            sell_amount = event['args']['sellAmount']
            if bet.exists():
                if sell_amount == bet.first().quantity:
                    print('bet:', bet.first())
                    bet.delete()
                else:
                    quantity = bet.first().quantity - sell_amount
                    Bid.objects.filter(id=bet.first().id).update(quantity=quantity)
                print('bet upgraded')

        print(f'{token} update!')
        price = token[0].price

        hell = TokenHistory.objects.filter(tx_hash=tx_hash)
        if hell.exists():
            hell.update(method='Buy', price=price)
        else:
            TokenHistory.objects.get_or_create(
                token=token[0],
                tx_hash=tx_hash,
                method='Buy',
                new_owner=new_owner,
                old_owner=old_owner,
                price=price
            )

    save_last_block(latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 
            f'BUY_LAST_BLOCK_{standart}')
    time.sleep(HOLDERS_CHECK_TIMEOUT)

    # else:
    #     print(f'\n Not enough block passed from block {block} \n')
    #     time.sleep(HOLDERS_CHECK_TIMEOUT)


def aproove_bet_scaner(latest_block, dds_contract):
    logging.basicConfig(level=logging.INFO, filename=f'logs/scaner_bet.log',
                    format='%(asctime)s %(levelname)s:%(message)s')
    block_count = HOLDERS_CHECK_CHAIN_LENGTH + HOLDERS_CHECK_COMMITMENT_LENGTH
    block = get_last_block(f'BET_LAST_BLOCK')
    logging.info(f'last block: {latest_block} \n block: {block}') 

    if latest_block - block > block_count:
        event_filter = dds_contract.events.Approval.createFilter(
            fromBlock=block,
            toBlock=latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH
        )
        
        events = event_filter.get_all_entries()

        if events:
            logging.info('have events!')

            for event in events:
                user = event['args']['src'].lower()
                exchange = event['args']['guy']
                logging.info(f'exchange: {exchange} \n user: {user}')

                if exchange == EXCHANGE['address']:
                    bet = Bid.objects.filter(user__username=user)
                    logging.info(f'bet: {bet}')

                    if bet.exists():
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
                    else:
                        logging.info('no bet! \n ___________')
                        continue
                else:
                    logging.info('not our wxchage')
        else:
            logging.info('no events! \n ___________')

        save_last_block(latest_block - HOLDERS_CHECK_COMMITMENT_LENGTH, 'BET_LAST_BLOCK')
        time.sleep(HOLDERS_CHECK_TIMEOUT)
        
    else:
        logging.info(f'\n Not enough block passed from block {block} \n ________________')
        time.sleep(HOLDERS_CHECK_TIMEOUT)


def scaner(smart_contract, standart=None):
    '''
    connects to the contract and calls scaners

    attributes:
        smart_contract - takes constant contract from local settigs
    '''

    # connect to provider and smart contract
    w3 = Web3(HTTPProvider('https://kovan.infura.io/v3/7b0399b88fc74f07ac9318ce9fc7f855'))
    dict_check = isinstance(smart_contract, dict)
    if dict_check:
        dds_contract = w3.eth.contract(
                        address=Web3.toChecksumAddress(smart_contract['address']),
                        abi=smart_contract['abi']
                )
    else:
        if smart_contract.standart == 'ERC721':
            abi = ERC721_MAIN['abi']
        elif smart_contract.standart == 'ERC1155':
            abi = ERC1155_MAIN['abi']
        dds_contract = w3.eth.contract(
            address=Web3.toChecksumAddress(smart_contract.address),
            abi=abi
        )

    while True:
        latest_block = w3.eth.blockNumber
        
        if smart_contract == ERC721_FABRIC or smart_contract == ERC1155_FABRIC:
            scan_deploy(latest_block, dds_contract, smart_contract)
        elif smart_contract == EXCHANGE:
            buy_scanner(latest_block, dds_contract, standart)
        elif smart_contract == WETH_CONTRACT:
            aproove_bet_scaner(latest_block, dds_contract)
        elif smart_contract.standart == 'ERC721' or smart_contract.standart == 'ERC1155':
            mint_transfer(latest_block, dds_contract, smart_contract)
