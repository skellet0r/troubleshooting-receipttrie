"""
"""
import json
import os

import rlp
from brownie import web3
from hexbytes import HexBytes
from trie import HexaryTrie
from web3.datastructures import AttributeDict
from web3.types import TxReceipt
from typing import Tuple, List
import io

PreparedLogs = List[Tuple[bytes, List[bytes], bytes]]
PreparedReceipt = Tuple[bytes, int, bytes, PreparedLogs]

# Some Random Transaction for Testing
# https://etherscan.io/tx/0x5abfd35ecf0de6d5675aab6eb7c5848ab4aaa579dcc935edbd3d02322fcab8e2
# TX_HASH = HexBytes("0x5abfd35ecf0de6d5675aab6eb7c5848ab4aaa579dcc935edbd3d02322fcab8e2")
# pre-berlin tx
TX_HASH = HexBytes("0x819e763e8cec7afaf63611aa43e4124a6ed69e272e9ff94eb1ad4cda29b4f6e5")


class ExtendedEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, HexBytes):
            return obj.hex()
        elif isinstance(obj, AttributeDict):
            return dict(obj)
        return json.JSONEncoder.default(self, obj)


def download_block_receipts(force=True) -> dict:
    """Download a block's transaction receipts and save to disk."""
    # fetch the tx related data
    tx = web3.eth.get_transaction(TX_HASH)
    tx_block = web3.eth.get_block(tx["blockNumber"])

    file_name = f"block-{tx['blockNumber']}-receipts.json"
    if not force and os.path.exists(file_name):
        with open(file_name) as f:
            return json.load(f)

    # generator for retrieving all the tx receipts in a block
    receipts = (
        web3.eth.get_transaction_receipt(_tx) for _tx in tx_block["transactions"]
    )

    with open(file_name, "w") as f:
        json.dump(list(receipts), f, indent=2, sort_keys=True, cls=ExtendedEncoder)

    return receipts


def prepare_receipt(receipt: TxReceipt) -> PreparedReceipt:
    """Prepare a transaction receipt for serialization"""
    receipt_root = HexBytes(receipt.get("root", b""))
    receipt_status = receipt.get("status", 1)

    receipt_root_or_status = receipt_root if len(receipt_root) > 0 else receipt_status
    receipt_cumulative_gas = receipt["cumulativeGasUsed"]
    receipt_logs_bloom = HexBytes(receipt["logsBloom"])
    receipt_logs = [
        (
            HexBytes(log["address"]),
            list(map(HexBytes, log["topics"])),
            HexBytes(log["data"]),
        )
        for log in receipt["logs"]
    ]

    return (
        receipt_root_or_status,
        receipt_cumulative_gas,
        receipt_logs_bloom,
        receipt_logs,
    )


def serialize_receipt(receipt: TxReceipt) -> bytes:
    prepared_receipt = prepare_receipt(receipt)
    encoded_receipt = rlp.encode(prepared_receipt)

    receipt_type = HexBytes(receipt.get("type", 0))
    if receipt_type == HexBytes(0):
        return encoded_receipt

    buffer = HexBytes(receipt_type) + encoded_receipt
    return rlp.encode(buffer)


def main():
    # fetch the tx related data
    tx = web3.eth.get_transaction(TX_HASH)
    tx_block = web3.eth.get_block(tx["blockNumber"])

    # initialize the trie
    trie = HexaryTrie({})

    # get all the tx receipts in a block
    receipts = download_block_receipts(force=False)

    # add each receipt to the receipts trie
    for tx_receipt in receipts:
        path = rlp.encode(tx_receipt["transactionIndex"])
        trie[path] = serialize_receipt(tx_receipt)

    a, b = trie.root_hash, tx_block["receiptsRoot"]
    err_msg = f"{a.hex()} != {b.hex()}"
    assert a == b, err_msg
