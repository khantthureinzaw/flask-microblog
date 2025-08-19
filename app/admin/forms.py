from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from flask_babel import _, lazy_gettext as _l
import sqlalchemy as sa

from app import db
from app.models import User

class ApprovePostForm(FlaskForm):
    submit = SubmitField(_l('Approve'))
    delete = SubmitField(_l('Delete'))

class DeletePostForm(FlaskForm):
    delete = SubmitField(_l('Delete'))

class CreateUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('analyst', 'Analyst'), ('user', 'User')], default='user')
    submit = SubmitField('Create User')

    def validate_username(self, username):
        user = db.session.scalar(
            sa.select(User).where(User.username == username.data)
        )
        if user is not None:
            raise ValidationError(_('Please use a different username.'))
        
    def validate_email(self, email):
        user = db.session.scalar(
            sa.select(User).where(User.email == email.data)
        )
        if user is not None:
            raise ValidationError(_('Please use a different email address.'))