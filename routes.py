from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import stripe
from models import REMITTANCE_FEES
from models import db, User, Transaction, MoneyRequest, add_block, remove_block, BankAccount

app = Blueprint('app', __name__)

# ✅ Home Page
@app.route('/')
def home():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('app.login'))
    
    user = User.query.get(user_id)
    pending_requests = MoneyRequest.query.filter_by(sender_email=user.email, status="Pending").all()
    transactions = Transaction.query.filter((Transaction.sender_id == user_id) | (Transaction.recipient_id == user_id)).all()
    print(transactions)
    return render_template('index.html', user=user, pending_requests=pending_requests, transactions=transactions)

@app.route('/add_money', methods=['POST'])
def add_money():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("app.login"))

    amount = int(request.form.get("amount")) * 100  # Convert to cents for Stripe

    stripe_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Wallet Deposit"},
                "unit_amount": amount
            },
            "quantity": 1
        }],
        mode="payment",
        success_url=url_for("app.add_money_success", _external=True, amount=amount),
        cancel_url=url_for("app.home", _external=True)  # Redirect home if canceled
    )

    return redirect(stripe_session.url, code=303)


@app.route('/add_money_success')
def add_money_success():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("app.login"))

    amount = int(request.args.get("amount", 0)) / 100  # Convert cents to dollars

    user = User.query.get(user_id)
    user.balance += amount
    db.session.commit()

    flash(f"Successfully added ${amount} to your wallet!", "success")
    return redirect(url_for("app.home"))

@app.route('/payment_success')
def payment_success():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("app.login"))

    amount = request.args.get("amount")  # Store the transaction amount safely
    add_block(user_id, float(amount))  # Add funds to blockchain
    flash("Funds added successfully!", "success")
    return redirect(url_for("app.home"))

@app.route('/withdraw_money', methods=['POST'])
def withdraw_money():
    if 'user_id' not in session:
        return redirect(url_for('app.login'))

    user = User.query.get(session['user_id'])
    amount = float(request.form['amount'])

    if amount > user.balance:
        flash("Insufficient balance!", "danger")
    else:
        user.balance -= amount
        db.session.commit()
        flash("Money withdrawn successfully!", "success")

    return redirect(url_for('app.home'))

# ✅ Send Money
@app.route('/send_money', methods=['POST'])
def send_money():
    sender_id = session.get('user_id')
    recipient_email = request.form['email']
    amount = float(request.form['amount'])

    sender = User.query.get(sender_id)
    recipient = User.query.filter_by(email=recipient_email).first()

    if not recipient:
        print("Recipient not found!", "danger")
        return redirect(url_for('app.payments'))

    if sender.balance < amount:
        print("Insufficient Balance!", "danger")
        return redirect(url_for('app.payments'))
    
    fee = round(amount * 0.005, 2)

    # Deduct sender balance & add to recipient
    sender.balance -= amount
    recipient.balance += amount-fee

    # Apply 0.5% transaction fee
    
    remove_block(sender_id, fee)  # Remove fee blocks

    # Update Blockchain
    remove_block(sender_id, amount)
    add_block(recipient.id, amount)

    transaction = Transaction(sender_id=sender.id, recipient_id=recipient.id, amount=amount-fee)
    db.session.add(transaction)
    db.session.commit()

    print(f"Transaction Successful! Fee deducted: ${fee}", "success")
    return redirect(url_for('app.payments'))

# ✅ Request Money
@app.route('/request_money', methods=['POST'])
def request_money():
    sender_id = session.get('user_id')
    recipient_email = request.form['email']
    amount = float(request.form['amount'])

    recipient = User.query.filter_by(email=recipient_email).first()
    if not recipient:
        print("User not found!", "danger")
        return redirect(url_for('app.payments'))
    
    money_request = MoneyRequest(sender_email=recipient_email, recipient_id=sender_id, amount=amount)
    db.session.add(money_request)
    db.session.commit()

    print("Money request sent successfully!", "success")
    return redirect(url_for('app.payments'))

# ✅ Accept Money Request
@app.route('/accept_request/<int:request_id>')
def accept_request(request_id):
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user_id:
        return redirect(url_for('app.login'))

    # Retrieve the money request by its ID
    money_request = MoneyRequest.query.get(request_id)
    if not money_request or money_request.sender_email != user.email:
        print("Invalid request!", "danger")
        return redirect(url_for('app.home'))
    
    # Current user (session user) is the payer
    payer = User.query.get(user_id)
    # The requester (the person who originally requested money) is identified by the sender_email field
    requester = User.query.get(money_request.recipient_id)

    if not requester:
        print("Requester not found!", "danger")
        return redirect(url_for('app.home'))

    if payer.balance < money_request.amount:
        print("Insufficient balance to fulfill the request!", "danger")
        return redirect(url_for('app.home'))

    # Deduct money from the payer and credit the requester
    payer.balance -= money_request.amount
    db.session.commit()
    requester.balance += money_request.amount
    db.session.commit()

    # Apply a 0.5% transaction fee (for blockchain fee purposes)
    fee = round(money_request.amount * 0.005, 2)
    remove_block(requester.id, fee)  # Remove fee blocks from payer

    # # Update Blockchain: remove blocks equal to the requested amount from payer, and add blocks for requester
    # remove_block(payer.id, money_request.amount)
    # add_block(requester.id, money_request.amount)

    # Record the transaction (assuming Transaction model exists)
    transaction = Transaction(sender_id=payer.id, recipient_id=requester.id, amount=money_request.amount)
    db.session.add(transaction)
    db.session.commit()

    # Mark the money request as accepted
    money_request.status = "Accepted"
    db.session.commit()

    print("Money request accepted!", "success")
    return redirect(url_for('app.home'))

# ✅ Payments Page
@app.route('/payments')
def payments():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('app.login'))
    
    user = User.query.get(user_id)
    transactions = Transaction.query.filter((Transaction.sender_id == user.id) | (Transaction.recipient_id == user.id)).all()
    people = set()
    
    for tx in transactions:
        people.add(User.query.get(tx.sender_id))
        people.add(User.query.get(tx.recipient_id))

    return render_template('payments.html', user=user, transactions=transactions, people=people)

COUNTRY_CODES = {
    "Bahrain": "bh", "Kuwait": "kw", "Oman": "om", "Qatar": "qa", "Saudi Arabia": "sa", "United Arab Emirates": "ae",
    "Jordan": "jo", "Lebanon": "lb", "Maldives": "mv", "Sri Lanka": "lk", "Bangladesh": "bd", "Philippines": "ph",
    "Malaysia": "my", "Thailand": "th", "Vietnam": "vn", "Indonesia": "id", "Cambodia": "kh", "Myanmar": "mm",
    "Laos": "la", "Taiwan": "tw", "Brunei": "bn", "Mongolia": "mn", "Afghanistan": "af", "Kazakhstan": "kz",
    "Cyprus": "cy", "Hong Kong": "hk", "Singapore": "sg", "Switzerland": "ch", "Monaco": "mc"
}


# ✅ User Page
@app.route('/user')
def user_page():
    user_id = session.get('user_id')
    banks = BankAccount.query.filter_by(user_id=user_id).all()
    if not user_id:
        return redirect(url_for('app.login'))
    
    user = User.query.get(user_id)
    return render_template('user.html', user=user, linked_accounts=banks, fees=REMITTANCE_FEES, country_codes=COUNTRY_CODES)

# ✅ Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            session['user_id'] = user.id
            return redirect(url_for('app.home'))
        
        print("Invalid credentials!", "danger")
    
    return render_template('login.html')

# ✅ Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        country = request.form['country']
        language = request.form['language']
        
        new_user = User(username=username, email=email, password=password, country=country, language=language)
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        return redirect(url_for('app.home'))
    
    return render_template('signup.html')

# ✅ Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('app.login'))

# New endpoint to link bank accounts
@app.route('/link_bank', methods=['GET', 'POST'])
def link_bank():
    if request.method == 'POST':
        user_id = session.get('user_id')
        if not user_id:
            flash("Please log in first!", "danger")
            return redirect(url_for('app.login'))
        
        bank_name = request.form.get('bank_name')
        account_number = request.form.get('account_number')
        ifsc_code = request.form.get('ifsc_code')
        account_type = request.form.get('account_type')
        branch_name = request.form.get('branch_name')

        # Check if the account already exists
        existing_account = BankAccount.query.filter_by(account_number=account_number).first()
        if existing_account:
            flash("This bank account is already linked!", "warning")
            return redirect(url_for('app.user_page'))

        # Save new bank account details
        new_account = BankAccount(
            user_id=user_id,
            bank_name=bank_name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            account_type=account_type,
            branch_name=branch_name
        )
        db.session.add(new_account)
        db.session.commit()

        flash("Bank account linked successfully!", "success")
        return redirect(url_for('app.user_page'))
    
    return render_template('link_bank.html')  # Form to input bank details