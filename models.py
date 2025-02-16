from flask_sqlalchemy import SQLAlchemy
import json, hashlib
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    language = db.Column(db.String(10), default="en")
    country = db.Column(db.String(100), nullable=False)

    sent_transactions = db.relationship('Transaction', 
                                        foreign_keys='Transaction.sender_id', 
                                        backref='sender', 
                                        lazy=True)

    received_transactions = db.relationship('Transaction', 
                                            foreign_keys='Transaction.recipient_id', 
                                            backref='recipient', 
                                            lazy=True)

    money_requests = db.relationship('MoneyRequest', 
                                     foreign_keys='MoneyRequest.recipient_id', 
                                     backref='request_recipient', 
                                     lazy=True)

    bank_accounts = db.relationship('BankAccount', backref='user', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class MoneyRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_email = db.Column(db.String(100), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Pending")  # Pending, Accepted, Rejected

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    data = db.Column(db.Text, nullable=False)
    previous_hash = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def compute_hash(self):
        """ Compute hash for the block """
        block_data = json.dumps({
            'index': self.index,
            'data': self.data,
            'previous_hash': self.previous_hash
        }, sort_keys=True)
        return hashlib.sha256(block_data.encode()).hexdigest()

def create_genesis_block(user_id):
    """ Creates the first block in the blockchain """
    genesis_block = Block(
        index=0,
        data="Genesis Block",
        previous_hash="0",
        user_id=user_id
    )
    genesis_block.previous_hash = genesis_block.compute_hash()
    db.session.add(genesis_block)
    db.session.commit()

def add_block(user_id, amount):
    """ Adds multiple blocks, one for each unit of amount added """
    last_block = Block.query.filter_by(user_id=user_id).order_by(Block.index.desc()).first()
    new_index = last_block.index + 1 if last_block else 1  # Genesis block check

    for _ in range(int(amount)):  # Create a block for each unit of amount
        new_block = Block(
            index=new_index,
            data=f"Added 1 USD",  # Each block represents 1 USD
            previous_hash=last_block.compute_hash() if last_block else "0",
            user_id=user_id
        )
        new_block.previous_hash = new_block.compute_hash()
        db.session.add(new_block)
        last_block = new_block  # Update last_block for the next iteration
        new_index += 1  # Increment index for the next block
    
    db.session.commit()

def remove_block(user_id, amount):
    """ Removes blocks when funds are withdrawn """
    blocks_to_remove = round(amount)  # Ensuring decimal amounts are handled
    user_blocks = Block.query.filter_by(user_id=user_id).order_by(Block.index.desc()).all()

    if len(user_blocks) < blocks_to_remove:
        print("❌ Insufficient blocks to remove")
        return False  # Not enough blocks to remove

    # Remove blocks safely
    for _ in range(min(blocks_to_remove, len(user_blocks))):
        db.session.delete(user_blocks.pop(0))  # Remove from latest to oldest

    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Error removing blocks: {e}")
        return False

class BankAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(50), unique=True, nullable=False)
    ifsc_code = db.Column(db.String(20), nullable=False)
    account_type = db.Column(db.String(20), nullable=False)  # Savings, Current, etc.
    branch_name = db.Column(db.String(100), nullable=False)

REMITTANCE_FEES = {
    "Bahrain": 0.5, "Kuwait": 0.5, "Oman": 0.5, "Qatar": 0.5, "Saudi Arabia": 0.5, "United Arab Emirates": 0.5,
    "Jordan": 0.5, "Lebanon": 0.5, "Maldives": 0.5, "Sri Lanka": 0.5, "Bangladesh": 0.5, "Philippines": 0.5,
    "Malaysia": 0.5, "Thailand": 0.5, "Vietnam": 0.5, "Indonesia": 0.5, "Cambodia": 0.5, "Myanmar": 0.5,
    "Laos": 0.5, "Taiwan": 0.5, "Brunei": 0.5, "Mongolia": 0.5, "Afghanistan": 0.5, "Kazakhstan": 0.5,
    "Cyprus": 0.5, "Hong Kong": 0.5, "Singapore": 0.5, "Switzerland": 0.5, "Monaco": 0.5
}