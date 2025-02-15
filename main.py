from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import time
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'secretkey'
db = SQLAlchemy(app)

# User Model# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    blockchain = db.relationship('Blockchain', backref='user', lazy=True, uselist=False)

    sent_requests = db.relationship('MoneyRequest', foreign_keys='MoneyRequest.sender_id', backref='request_sender', lazy=True)
    received_requests = db.relationship('MoneyRequest', foreign_keys='MoneyRequest.receiver_id', backref='request_receiver', lazy=True)

# Blockchain Model
class Blockchain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chain = db.Column(db.Text, nullable=False, default=json.dumps([]))
# Money Request Model
class MoneyRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rejected'

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])

# Blockchain System
class BlockchainSystem:
    def __init__(self, chain=None):
        self.chain = json.loads(chain) if chain else []
        if not self.chain:
            self.create_block(previous_hash='0')

    def create_block(self, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'previous_hash': previous_hash
        }
        self.chain.append(block)
        return block

    def hash(self, block):
        return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

# Create database tables
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        blockchain = Blockchain(user_id=new_user.id, chain=json.dumps(BlockchainSystem().chain))
        db.session.add(blockchain)
        db.session.commit()

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    money_requests = MoneyRequest.query.filter_by(receiver_id=user.id, status='pending').all()
    return render_template('dashboard.html', user=user, money_requests=money_requests)

@app.route('/add_money', methods=['POST'])
def add_money():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    amount = float(request.form['amount'])
    user = User.query.get(session['user_id'])
    user.balance += amount

    blockchain = Blockchain.query.filter_by(user_id=user.id).first()
    bc_system = BlockchainSystem(blockchain.chain)

    for _ in range(int(amount)):
        previous_hash = bc_system.hash(bc_system.chain[-1])
        bc_system.create_block(previous_hash)

    blockchain.chain = json.dumps(bc_system.chain)
    db.session.commit()
    
    return redirect(url_for('dashboard'))

@app.route('/send_money', methods=['POST'])
def send_money():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    recipient_email = request.form['email']
    amount = float(request.form['amount'])
    sender = User.query.get(session['user_id'])
    recipient = User.query.filter_by(email=recipient_email).first()

    if recipient and sender.balance >= amount:
        sender.balance -= amount
        recipient.balance += amount

        sender_blockchain = Blockchain.query.filter_by(user_id=sender.id).first()
        recipient_blockchain = Blockchain.query.filter_by(user_id=recipient.id).first()

        sender_bc_system = BlockchainSystem(sender_blockchain.chain)
        recipient_bc_system = BlockchainSystem(recipient_blockchain.chain)

        for _ in range(int(amount)):
            previous_hash_sender = sender_bc_system.hash(sender_bc_system.chain[-1])
            previous_hash_recipient = recipient_bc_system.hash(recipient_bc_system.chain[-1])
            sender_bc_system.create_block(previous_hash_sender)
            recipient_bc_system.create_block(previous_hash_recipient)

        sender_blockchain.chain = json.dumps(sender_bc_system.chain)
        recipient_blockchain.chain = json.dumps(recipient_bc_system.chain)
        db.session.commit()

    return redirect(url_for('dashboard'))

@app.route('/request_money', methods=['POST'])
def request_money():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    receiver_email = request.form['email']
    amount = float(request.form['amount'])
    sender = User.query.get(session['user_id'])
    receiver = User.query.filter_by(email=receiver_email).first()

    if receiver:
        money_request = MoneyRequest(sender_id=sender.id, receiver_id=receiver.id, amount=amount)
        db.session.add(money_request)
        db.session.commit()

    return redirect(url_for('dashboard'))

@app.route('/handle_request/<int:request_id>/<action>', methods=['POST'])
def handle_request(request_id, action):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    money_request = MoneyRequest.query.get(request_id)
    if not money_request or money_request.receiver_id != session['user_id']:
        return redirect(url_for('dashboard'))
    
    if action == 'accept':
        sender = User.query.get(money_request.sender_id)
        receiver = User.query.get(money_request.receiver_id)

        if receiver.balance >= money_request.amount:
            receiver.balance -= money_request.amount
            sender.balance += money_request.amount
            money_request.status = 'accepted'
        else:
            money_request.status = 'rejected'
    
    elif action == 'reject':
        money_request.status = 'rejected'
    
    db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')