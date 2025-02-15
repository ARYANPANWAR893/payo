from flask import Flask, request, jsonify, render_template, redirect, url_for
import hashlib
import time
import json

app = Flask(__name__)

# Blockchain class
class Blockchain:
    def __init__(self):
        self.chain = []
        self.transactions = []
        self.create_block(proof=1, previous_hash='0')

    def create_block(self, proof, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.transactions,
            'proof': proof,
            'previous_hash': previous_hash
        }
        self.transactions = []
        self.chain.append(block)
        return block

    def add_transaction(self, sender, receiver, amount):
        self.transactions.append({
            'sender': sender,
            'receiver': receiver,
            'amount': amount
        })
        return self.last_block['index'] + 1

    def proof_of_work(self, previous_proof):
        new_proof = 1
        check_proof = False
        while not check_proof:
            hash_operation = hashlib.sha256(str(new_proof**2 - previous_proof**2).encode()).hexdigest()
            if hash_operation[:4] == '0000':
                check_proof = True
            else:
                new_proof += 1
        return new_proof

    def hash(self, block):
        return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

# Instantiate blockchain
blockchain = Blockchain()

@app.route('/')
def home():
    return render_template('index.html', chain=blockchain.chain)

@app.route('/mine_block', methods=['GET'])
def mine_block():
    previous_block = blockchain.last_block
    previous_proof = previous_block['proof']
    proof = blockchain.proof_of_work(previous_proof)
    previous_hash = blockchain.hash(previous_block)
    block = blockchain.create_block(proof, previous_hash)
    return redirect(url_for('home'))

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    data = request.form
    required_fields = ['sender', 'receiver', 'amount']
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing fields'}), 400
    index = blockchain.add_transaction(data['sender'], data['receiver'], data['amount'])
    return redirect(url_for('home'))

@app.route('/get_chain', methods=['GET'])
def get_chain():
    response = {'chain': blockchain.chain, 'length': len(blockchain.chain)}
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(debug=True)