from tronapi import Tron, HttpProvider


class Scanner:
    ...

    def get_last_network_block(self):
        provider = HttpProvider(self.endpoint)
        tron = Tron(
            full_node=provider,
            solidity_node=provider,
            event_server=provider,
        )
        return tron.trx.get_block('latest')['block_header']['raw_data']
