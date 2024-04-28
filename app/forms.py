from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectMultipleField, TextAreaField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
from wtforms import widgets
import sqlalchemy as sa
from app import db
from app.models import User
from wtforms.validators import Length
from flask_login import current_user
from flask_wtf.file import FileField
import imghdr
from markupsafe import Markup
from flask import request



class LoginForm(FlaskForm):
    username_or_email = StringField('Username or Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if user is not None:
            raise ValidationError('Please use a different username.')
        for character in username.data:
            if not (character.isnumeric() or character.isspace() or character.isalpha() or character == "_"):
                raise ValidationError('Special characters (!@#$ etc) are invalid.')
            if character.isspace():
                raise ValidationError('Spaces are invalid.')
            
    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(
            User.email == email.data))
        if user is not None:
            raise ValidationError('Please use a different email address.')
        
    def validate_password(self, password):
        if len(password.data) < 12:
            raise ValidationError('Make sure you use at least 12 characters.')
        alpha = False
        num = False
        special = False
        for character in password.data:
            if not (character.isnumeric() or character.isspace() or character.isalpha()):
                special = True
            elif character.isnumeric():
                num = True
            elif character.isalpha():
                alpha = True
        check = all([alpha,num,special])
        if check == False:
            raise ValidationError('Make sure you use at least 1 letter, 1 number and 1 special character (!@#$ etc).')

 

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    about_me = TextAreaField('About me', validators=[Length(min=0, max=336)])
    profile_pic = FileField('Profile Picture')
    checkbox = BooleanField('Use Default Picture')
    submit = SubmitField('Submit')

    def validate_username(self, username):
        original_username = current_user.username
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if original_username!=username.data:
            if user is not None:
                raise ValidationError('This username already exists. Please use a different username.')
            
    def validate_profile_pic(self, profile_pic):
        if profile_pic.data:
            if imghdr.what(profile_pic.data) is None:
                    raise ValidationError('Please use an image file.')



class BootstrapListWidget(widgets.ListWidget):
    def __call__(self, field, **kwargs):
        kwargs.setdefault("id", field.id)
        html = [f"<{self.html_tag} {widgets.html_params(**kwargs)}>"]
        for subfield in field:
            if self.prefix_label:
                html.append(f"<li class='list-group-item'>{subfield.label} {subfield(class_='form-check-input ms-1')}</li>")
            else:
                html.append(f"<li class='list-group-item'>{subfield(class_='form-check-input me-1')} {subfield.label}</li>")
        html.append("</%s>" % self.html_tag)
        return Markup("".join(html))

class MultiCheckboxField(SelectMultipleField):
    widget = BootstrapListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

    
class PostForm(FlaskForm):
    title = StringField('Title', validators=[Length(min=0, max=99), DataRequired()])
    category = MultiCheckboxField(u'Category', choices=[('NEWS', 'NEWS'), ('MEDIA', 'MEDIA'), ('SHOWBIZ', 'SHOWBIZ'), ('SPORTS', 'SPORTS'), ('VIRAL', 'VIRAL')])
    body = TextAreaField('Write your article...', validators=[Length(min=0, max=7000), DataRequired()])
    lead_in = TextAreaField('Write a lead-in text to additional content... (optional)', validators=[Length(min=0, max=170)])
    post_pic = FileField('Image')
    checkbox = BooleanField('Use Default Picture')
    submit = SubmitField('Submit')

            
    def validate_post_pic(self, post_pic):
        if post_pic.data:
            if imghdr.what(post_pic.data) is None:
                    raise ValidationError('Please use an image.')
            

    def validate_category(self, category):
        if len(category.data) == 0:
            raise ValidationError('Please select at least one of the category options.')
        

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Request Password Reset')

    def validate_password(self, password):
        if len(password.data) < 12:
            raise ValidationError('Make sure you use at least 12 characters.')
        alpha = False
        num = False
        special = False
        for character in password.data:
            if not (character.isnumeric() or character.isspace() or character.isalpha()):
                special = True
            elif character.isnumeric():
                num = True
            elif character.isalpha():
                alpha = True
        check = all([alpha,num,special])
        if check == False:
            raise ValidationError('Make sure you use at least 1 letter, 1 number and 1 special character (!@#$ etc).')



class SearchForm(FlaskForm):
    q = StringField(('Search'), validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'meta' not in kwargs:
            kwargs['meta'] = {'csrf': False}
        super(SearchForm, self).__init__(*args, **kwargs)