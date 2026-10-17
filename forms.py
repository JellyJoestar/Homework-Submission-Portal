from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class RubricCriterionForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[DataRequired()])
    weight = StringField("Weight (%)", validators=[DataRequired()])
    submit = SubmitField("Save Criterion")


class RubricActionForm(FlaskForm):
    """CSRF protection for rubric delete actions."""
