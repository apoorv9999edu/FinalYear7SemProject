import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4
import requests
from flask import Flask, jsonify, request, render_template, redirect
import sqlite3 as sql
from datetime import datetime
import pytz
from pytz import timezone
ist_tz = pytz.timezone('Asia/Kolkata')

class Blockchain:
    def __init__(self):
        self.current_transactions = []
        self.chain = []
        self.nodes = set()

        # Create the genesis block
        self.new_block(previous_hash='1', proof=100)

    def register_node(self, address):
        """
        Add a new node to the list of nodes
        :param address: Address of node. Eg. 'http://192.168.0.5:5000'
        """

        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            # Accepts an URL without scheme like '192.168.0.5:5000'.
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')


    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid

        :param chain: A blockchain
        :return: True if valid, False if not
        """
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Check that the hash of the block is correct
            last_block_hash = self.hash(last_block)
            if block['previous_hash'] != last_block_hash:
                return False

            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof'], last_block_hash):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        This is our consensus algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.

        :return: True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, previous_hash):
        """
        Create a new Block in the Blockchain

        :param proof: The proof given by the Proof of Work algorithm
        :param previous_hash: Hash of previous Block
        :return: New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': str(datetime.now(ist_tz)),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash,
        }
        guess = f'{proof}{previous_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        print(guess_hash)
        # Reset the current list of transactions
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self,id,sender,reciever,type):
        """
        Creates a new transaction to go into the next mined Block
        :param sender: Address of the Sender
        :param recipient: Address of the Recipient
        :param amount: Amount
        :return: The index of the Block that will hold this transaction
        """
        self.current_transactions.append({
            'id': id,
            'sender': sender,
            'reciever': reciever,
            'block_index': 'a',
            'time': str(datetime.now(ist_tz)),
            'type':type,
        })
        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        # Calulates hash of the Block
        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_block):
        """
        Simple Proof of Work Algorithm:

         - Find a number p' such that hash(pp') contains leading 4 zeroes
         - Where p is the previous proof, and p' is the new proof
         
        :param last_block: <dict> last Block
        :return: <int>
        """

        last_hash = self.hash(last_block)

        proof = 0
        while self.valid_proof(proof, last_hash) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(proof, last_hash):
        """
        Validates the Proof

        :param proof: <int> Current Proof
        :param last_hash: <str> The hash of the Previous Block
        :return: <bool> True if correct, False if not.

        """
        guess = f'{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"


# Instantiate the Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()
# con = sqlite3.connect('database.db')


@app.route('/mine', methods=['GET'])
def mine():
    try:
        last_block = blockchain.last_block
        proof = blockchain.proof_of_work(last_block)
        previous_hash = blockchain.hash(last_block)
        block = blockchain.new_block(proof,previous_hash)
        con = sql.connect('database.db')
        for transaction in block['transactions']:
            transaction['block_index']=block['index']
            cur = con.cursor()
            cur.execute("INSERT INTO tb(id,sender,reciever,block_index,time,type) VALUES (?,?,?,?,?,?)",(transaction['id'],transaction['sender'],transaction['reciever'],transaction['block_index'],transaction['time'],transaction['type']) )
        response = {
            'message': "New Block Forged",
            'index': block['index'],
            'transactions': block['transactions'],
            'proof': block['proof'],
            'previous_hash': block['previous_hash']
            }
        con.commit()
        return jsonify(response), 200
    except:
        return jsonify('Error'), 404


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    try:
        values = request.get_json()
        index = blockchain.new_transaction(values['id'], values['sender'], values['reciever'],values['type'])
        response = {'message': f'Transaction will be added to Block {index}'}
        return jsonify(response), 201
    except:
        return 'Missing values', 400


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/chain/<int:block_no>', methods=['GET'])
def only_block(block_no):
    if (len(blockchain.chain)<block_no or block_no==0):
        return jsonify('No Such Block'), 404
    else:    
        response = {
            'chain': blockchain.chain[block_no-1],
        }
        return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200




@app.route('/', methods=['GET','POST'])
def page():
    return render_template('index.html')

@app.route('/asset', methods=['GET','POST'])
def asset_page():
    if request.method == 'POST':
        try:
            con = sql.connect("database.db")
            cur = con.cursor()
            id = request.form['id']
            cur.execute(f"select * from tb where id='{id}' AND type='a' ORDER BY time DESC")
            rows = cur.fetchall()
            con.close()
            return render_template('asset.html',rows=rows)
        except:
            return redirect('/asset')
    else :
        rows = []
        return render_template('asset.html',rows=rows)

@app.route('/vial', methods=['GET','POST'])
def vial_page():
    if request.method == 'POST':
        try :
            con = sql.connect("database.db")
            cur = con.cursor()
            id = request.form['id']
            cur.execute(f"select * from tb where id='{id}' and type='v' ORDER BY time DESC")
            rows = cur.fetchall()
            con.close()
            return render_template('vial.html',rows=rows)
        except:
            return redirect('/vial')
    else :
        rows = []
        return render_template('vial.html',rows=rows)
    return render_template('vial.html')

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@app.route('/api/vial/<string:id>', methods=['GET'])
def vial_details(id):
    try:
        con = sql.connect("database.db")
        con.row_factory = dict_factory
        cur = con.cursor()
        cur.execute(f"select * from tb where id='{id}' AND type='v' ORDER BY time DESC")
        rows = cur.fetchall()
        for x in rows:
            x.pop('type')
            x.pop('id')
        con.close()
        return jsonify(rows), 200
    except:
        return jsonify('Not Found'), 404

@app.route('/api/asset/<string:id>', methods=['GET'])
def asset_details(id):
    try:
        con = sql.connect("database.db")
        con.row_factory = dict_factory
        cur = con.cursor()
        cur.execute(f"select * from tb where id='{id}' AND type='a' ORDER BY time DESC")
        rows = cur.fetchall()
        for x in rows:
            x.pop('type')
            x.pop('id')
        con.close()
        return jsonify(rows), 200
    except:
        return jsonify('Not Found'), 404

if __name__ == '__main__':
    '''
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port 
    '''
    app.run(debug=1)
