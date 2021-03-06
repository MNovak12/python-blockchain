import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify
from flask import request


class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        # Genesis block
        self.new_block(100, 1)

    def register_node(self, address):
        # add a new node to the list of nodes
        url = urlparse(address)
        self.nodes.add(url.netloc)

    def new_block(self, proof, previous_hash=None):
        # Creates a new Block and adds it to the chain
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }

        # Reset current transactions
        self.current_transactions = []

        self.chain.append(block)
        return block

    def valid_chain(self, chain):
        # check that the blockchain is valid
        last_block = chain[0]
        curr_idx = 1

        while curr_idx < len(chain):
            block = chain[curr_idx]

            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")

            # check that the hash and proof of work are correct
            if block['previous_hash'] != self.hash(block):
                return False
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            curr_idx += 1
            last_block = block

        return True

    def resolve_conflicts(self):
        # the longest chain is the correct one
        max_len = len(self.chain)
        new_chain = None

        for node in self.nodes:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_len:
                    max_len = length
                    new_chain = chain

        # replace our chain with the longer one if it exists
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_transaction(self, sender, recipient, amount):
        # Adds a new transaction to the list of transactions
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        # Hashes a Block
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        # Returns the last Block in the chain
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """
        Simple Proof of Work Algorithm:
         - Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
         - p is the previous proof, and p' is the new proof
        From https://hackernoon.com/learn-blockchains-by-building-one-117428612f46
        :param last_proof: <int>
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Validates the Proof: Does hash(last_proof, proof) contain 4 leading zeroes?
        From https://hackernoon.com/learn-blockchains-by-building-one-117428612f46
        :param last_proof: <int> Previous Proof
        :param proof: <int> Current Proof
        :return: <bool> True if correct, False if not.
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == '0000'


# Instantiate our Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # reward with a new coin
    blockchain.new_transaction(
        sender='0',
        recipient=node_identifier,
        amount=1
    )

    # add a new block with previous unverified transactions and transaction containing reward coin
    previous_hash = blockchain.hash(last_block)
    response = blockchain.new_block(proof, previous_hash)
    response['message'] = 'New block added'
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    required = ['sender', 'recipient', 'amount']
    for value in required:
        if not value in values:
            return 'Missing ' + value

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')

    if not nodes:
        return 'Error: Please supply a valid list of nodes', 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': len(nodes)
    }

    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our blockchain was replaced',
            'new_blockchain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our blockchain was correct',
            'blockchain': blockchain.chain
        }
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
