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
        self.new_block(previous_hash='1', proof=100)


    def new_block(self, proof, previous_hash):
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
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self,id,sender,reciever,type):
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
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self,last_block):
        last_hash = self.hash(last_block)
        proof = 0
        while self.valid_proof(proof,last_hash) is False:
            proof += 1
        return proof

    def valid_proof(self,proof,last_hash):
        guess = f'{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

app = Flask(__name__)

# Instantiate the Blockchain
blockchain = Blockchain()

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


@app.route('/api/transaction/new', methods=['POST'])
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

@app.route('/api/details/', methods=['POST'])
def all_details():
    try:
        values = request.get_json()
        type = values['type']
        id = values['id']
        con = sql.connect("database.db")
        con.row_factory = dict_factory
        cur = con.cursor()
        if (type=="v"):
            cur.execute(f"select * from tb where id='{id}' AND type='v' ORDER BY time DESC")
        elif (type=="a"):
            cur.execute(f"select * from tb where id='{id}' AND type='a' ORDER BY time DESC")
        elif (type=="d"):
            cur.execute(f"select * from tb where sender='{id}' AND type='v' ORDER BY time DESC")
        elif (type=="p"):
            cur.execute(f"select * from tb where reciever='{id}' AND type='v' ORDER BY time DESC")
        else:
            return jsonify('Not Record Found'), 404
        rows = cur.fetchall()
        for x in rows:
            x.pop('type')
        con.close()
        return jsonify(rows), 200
    except:
        return jsonify('Not Record Found'), 404

if __name__ == '__main__':
    app.run(debug=1)
