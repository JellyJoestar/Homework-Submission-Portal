from functools import wraps
from flask import abort
from flask_login import login_required, current_user


def teacher_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.has_role("Teacher"):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.has_role("Student"):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
