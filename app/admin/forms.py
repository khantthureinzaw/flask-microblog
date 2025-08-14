from flask_wtf import FlaskForm
from wtforms import SubmitField
from flask_babel import _, lazy_gettext as _l

class ApprovePostForm(FlaskForm):
    submit = SubmitField(_l('Approve'))
    delete = SubmitField(_l('Delete'))

class DeletePostForm(FlaskForm):
    delete = SubmitField(_l('Delete'))