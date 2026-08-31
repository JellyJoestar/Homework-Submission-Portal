import os

from flask import Flask
from dotenv import load_dotenv

from views import views

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

app.register_blueprint(views)

if __name__ == "__main__":
    app.run(debug=True)
