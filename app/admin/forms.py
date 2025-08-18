from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from flask_babel import _, lazy_gettext as _l

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