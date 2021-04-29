import rlp
from brownie import web3
from trie import HexaryTrie
from web3.types import TxReceipt
from hexbytes import HexBytes


def serialize_receipt(receipt: TxReceipt) -> HexBytes:
    """Serialize a transaction receipt"""
    receipt_type = HexBytes(receipt.get("type", 0))
    receipt_status = HexBytes(receipt.get("root", receipt["status"]))
    receipt_cumulative_gas = receipt["cumulativeGasUsed"]
    receipt_logs_bloom = receipt["logsBloom"]
    receipt_logs = [
        (HexBytes(log["address"]), log["topics"], HexBytes(log["data"]))
        for log in receipt["logs"]
    ]

    data = [receipt_status, receipt_cumulative_gas, receipt_logs_bloom, receipt_logs]
    encoded = rlp.encode(data)

    if int.from_bytes(receipt_type, "big") != 0:
        return receipt_type + HexBytes(encoded)  # typed receipt EIP-2718
    return HexBytes(encoded)  # legacy receipt


# Some Random Transaction for Testing
# https://etherscan.io/tx/0x5abfd35ecf0de6d5675aab6eb7c5848ab4aaa579dcc935edbd3d02322fcab8e2
TX_HASH = HexBytes("0x5abfd35ecf0de6d5675aab6eb7c5848ab4aaa579dcc935edbd3d02322fcab8e2")


def main():
    # fetch the tx related data
    tx = web3.eth.get_transaction(TX_HASH)
    tx_block = web3.eth.get_block(tx["blockNumber"])

    # initialize the trie
    trie = HexaryTrie({})

    # generator for retrieving all the tx receipts in a block
    receipts = (
        web3.eth.get_transaction_receipt(_tx) for _tx in tx_block["transactions"]
    )

    # add each receipt to the receipts trie
    for tx_receipt in receipts:
        path = rlp.encode(tx_receipt["transactionIndex"])
        trie[path] = serialize_receipt(tx_receipt)

    err_msg = f"{trie.root_hash.hex()} != {tx_block['receiptsRoot'].hex()}"
    assert trie.root_hash == tx_block["receiptsRoot"], err_msg
