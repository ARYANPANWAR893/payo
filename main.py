from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from routes import app as app_routes
from models import db
import stripe

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'secretkey'
app.config.from_object('config')
stripe.api_key = app.config["STRIPE_SECRET_KEY"]

db.init_app(app)
migrate = Migrate(app, db)

# Register routes
app.register_blueprint(app_routes)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host="127.0.0.1", port=5000, debug=True)
