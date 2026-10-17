import os, time

from flask import Flask
from dotenv import load_dotenv

from auth import auth, login_manager
from views import views
from preview.routes import preview
from rubric.routes import rubric
from rubric.grading_routes import grading

load_dotenv()

os.environ["TZ"] = "Australia/Brisbane"
if hasattr(time, "tzset"):  # not available on Windows, where the laptop's time is used
    time.tzset()
    
app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

login_manager.init_app(app)

app.register_blueprint(auth)
app.register_blueprint(views)
app.register_blueprint(preview)
app.register_blueprint(rubric)
app.register_blueprint(grading)

if __name__ == "__main__":
    app.run(debug=True)
