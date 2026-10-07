from urllib.parse import urlparse
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user
)
from db import get_user_by_email, get_user_by_id
from forms import LoginForm
from models import User

auth = Blueprint("auth", __name__)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str):
    # Called on every request to rebuild current_user from the session cookie
    return get_user_by_id(int(user_id))


@auth.after_app_request
def disable_cache_for_logged_users(response):
    # Stops the browser "back" button from showing protected pages after logout
    if current_user.is_authenticated:
        response.headers["Cache-Control"] = "no-store"
    return response


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect_for_role(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        user = get_user_by_email(form.email.data)
        if user and user.check_password(form.password.data):
            login_user(user)
            next_url = request.args.get("next")
            # Only follow relative URLs, so ?next= can't send users to another site
            if next_url and urlparse(next_url).netloc == "":
                return redirect(next_url)
            return redirect_for_role(user)
        flash("Invalid email or password.", "error")
        return render_template("login.html", form=form), 401

    if request.method == "POST":
        return render_template("login.html", form=form), 400
    return render_template("login.html", form=form)


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


def redirect_for_role(user: User):
    if user.has_role("Teacher"):
        return redirect(url_for("views.teacher_assessments"))
    return redirect(url_for("views.student_home"))
