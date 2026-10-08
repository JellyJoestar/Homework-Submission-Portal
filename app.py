import os

from flask import Flask
from dotenv import load_dotenv

from auth import auth, login_manager
from views import views

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

login_manager.init_app(app)

app.register_blueprint(auth)
app.register_blueprint(views)

if __name__ == "__main__":
    app.run(debug=True)
