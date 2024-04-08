from flask import render_template, flash, redirect, url_for
from app import app
from app.forms import LoginForm, RegistrationForm, EditProfileForm, PostForm, ResetPasswordRequestForm, ResetPasswordForm
from flask_login import current_user, login_user
import sqlalchemy as sa
from app import db
from app.models import User, Post
from flask_login import logout_user
from flask_login import login_required
from flask import request
from urllib.parse import urlsplit
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
import uuid as uuid 
import os
from app.email import send_password_reset_email



@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()


@app.route('/')
@app.route('/index')
def index():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('index', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template("index.html", title='Home', posts=posts.items, next_url=next_url, prev_url=prev_url)



@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username_or_email.data))
        if user is None:
            user = db.session.scalar(
            sa.select(User).where(User.email == form.username_or_email.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/profile/<username>')
def profile(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    num_posts = len(db.session.scalars(user.posts.select()).all())
    page = request.args.get('page', 1, type=int)
    query = user.posts.select().order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'],
                        error_out=False)
    next_url = url_for('profile', username=user.username, page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('profile', username=user.username, page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('profile.html', user=user, num_posts=num_posts, posts=posts.items, next_url=next_url, prev_url=prev_url)



@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        pic = form.profile_pic.data
        if pic:
            pic_name = str(uuid.uuid1()) + "_" + secure_filename(pic.filename)
            pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
            current_user.profile_pic = pic_name
            db.session.commit()
            flash('Your changes have been saved.')
            return redirect(url_for('profile', username=current_user.username))
        else:
            db.session.commit()
            flash('Your changes have been saved.')
            return redirect(url_for('profile', username=current_user.username))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
        form.profile_pic.data  = current_user.profile_pic
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)


@app.route('/delete_profile_picture', methods=['GET','POST'])
@login_required
def delete_profile_picture():
    current_user.profile_pic = None
    db.session.commit()
    flash('Your profile picture was deleted successfully.')
    return redirect(url_for('profile', username=current_user.username))
    



@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        title = form.title.data
        body = form.body.data
        lead_in = form.lead_in.data
        post = Post(title=title, body=body, lead_in=lead_in, user_id=current_user.id)
        db.session.add(post)       
        db.session.commit()
        query = sa.select(Post).where(Post.user_id==current_user.id).order_by(Post.id.desc())
        post = db.session.scalars(query).first()
        category = form.category.data
        for c in category:
            if c == 'NEWS':
                post.news = 1
            if c == 'MEDIA':
                post.media = 1
            if c == 'SHOWBIZ':
                post.showbiz = 1
            if c == 'SPORTS':
                post.sports = 1
            if c == 'VIRAL':
                post.viral = 1
        db.session.commit()
        pic = form.post_pic.data
        if pic:
            pic_name = str(uuid.uuid1()) + "_" + secure_filename(pic.filename)
            pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
            post.post_pic = pic_name
            db.session.commit()
        flash('Your post has been uploaded.')
        return redirect(url_for('post', id=post.id))
    return render_template('create_post.html', title='New Post', h='New Post',
                           form=form)


@app.route('/post/<id>')
def post(id):
    post = db.first_or_404(sa.select(Post).where(Post.id == id))
    query = sa.select(Post).where((Post.media==1)&(Post.id!=post.id)).order_by(Post.timestamp.desc())
    posts_media1 = db.session.scalars(query).all()[:4]
    posts_media2 = db.session.scalars(query).all()[5:8]
    return render_template('post.html', post=post, posts_media1=posts_media1, posts_media2=posts_media2)


@app.route('/edit_post/<id>', methods=['GET', 'POST'])
@login_required
def edit_post(id):
    post = db.first_or_404(sa.select(Post).where(Post.id == id))
    if post.author == current_user:
        form = PostForm()
        if form.validate_on_submit():
            post.title = form.title.data
            post.body = form.body.data
            post.lead_in = form.lead_in.data
            post.news = None  
            post.media = None
            post.showbiz = None
            post.sports = None
            post.viral = None    
            categ = form.category.data
            for c in categ:
                if c == 'NEWS':
                    post.news = 1
                if c == 'MEDIA':
                    post.media = 1
                if c == 'SHOWBIZ':
                    post.showbiz = 1
                if c == 'SPORTS':
                    post.sports = 1
                if c == 'VIRAL':
                    post.viral = 1
            pic = form.post_pic.data
            if pic:
                pic_name = str(uuid.uuid1()) + "_" + secure_filename(pic.filename)
                pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
                post.post_pic = pic_name
                db.session.commit()
                flash('Your changes have been saved.')
                return redirect(url_for('post', id=post.id))
            else:
                db.session.commit()
                flash('Your changes have been saved.')
                return redirect(url_for('post', id=post.id))
        elif request.method == 'GET':
            form.title.data = post.title
            form.body.data = post.body
            form.lead_in.data = post.lead_in
            category = []
            if post.news:
                category.append('NEWS')
            if post.media:
                category.append('MEDIA')
            if post.showbiz:
                category.append('SHOWBIZ')
            if post.sports:
                category.append('SPORTS')
            if post.viral:
                category.append('VIRAL')
            form.category.data = category
            form.post_pic.data  = post.post_pic
        return render_template('create_post.html', title='Edit Post', h='Edit Post',
                            form=form, id=post.id)
    else:
        error="You cannot edit the post of another user!"
        return render_template('error.html', error=error)


@app.route('/delete_image/<id>', methods=['GET','POST'])
@login_required
def delete_image(id):
    post = db.first_or_404(sa.select(Post).where(Post.id == id))
    if post.author == current_user:
        post.post_pic =None   
        db.session.commit()
        flash("Your post's image has been deleted.")
        return redirect(url_for('post', id=post.id))
    else:
        error="You cannot edit the post of another user!"
        return render_template('error.html', error=error)



@app.route('/delete_post/<id>', methods=['GET', 'POST'])
@login_required
def delete_post(id):
    post = db.first_or_404(sa.select(Post).where(Post.id == id))
    if post.author == current_user:
        db.session.delete(post)       
        db.session.commit()
        flash('Your post has been deleted.')
        return redirect(url_for('profile', username=current_user.username))
    else:
        error="You cannot delete the post of another user!"
        return render_template('error.html', error=error)


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data))
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

