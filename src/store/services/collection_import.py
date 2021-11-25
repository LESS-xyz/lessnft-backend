from web3.exceptions import ContractLogicError
from src.store.models import Collection


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

    @property
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
        print([hasattr(self.contract_function, attr) for attr in attrs])
        print(dir(self.contract_function))
        if all([hasattr(self.contract_function, attr) for attr in attrs]):
            return True
        return False

    def is_valid(self) -> bool:
        if not self.is_total_supply_valid:
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