from flask import render_template, flash, redirect, url_for, jsonify
from app import app
from app.forms import LoginForm, RegistrationForm, EditProfileForm, PostForm, ResetPasswordRequestForm, ResetPasswordForm, SearchForm, CommentForm, ReplyForm
from flask_login import current_user, login_user
import sqlalchemy as sa
from app import db
from app.models import User, Post, Like, Comment, Like_Comment, Notification, Notification_Call
from flask_login import logout_user
from flask_login import login_required
from flask import request
from urllib.parse import urlsplit
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
import uuid as uuid 
import os
from app.email import send_password_reset_email
from flask import g
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError
from elasticsearch.exceptions import ConnectionTimeout as ConnectionTimeoutError
from sqlalchemy import func




@app.before_request
def before_request():
    g.search_form = SearchForm()
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()


@app.route('/')
@app.route('/index')
def index():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).order_by(Post.timestamp.desc())
    posts = db.session.scalars(query).all()
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('index', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) \
        if posts.has_prev else None 
    return render_template("index.html", title='Home', posts=posts.items, next_url=next_url, prev_url=prev_url, current_user=current_user)



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
    return render_template('profile.html', title='Profile', user=user, num_posts=num_posts, posts=posts.items, next_url=next_url, prev_url=prev_url, current_user=current_user)



@app.route('/profile/<username>/likes')
def likes(username):
    page = request.args.get('page', 1, type=int)
    user = db.first_or_404(sa.select(User).where(User.username == username))
    query = sa.select(Post).join(Like).where(Like.user_id==user.id).order_by(Like.timestamp.desc())
    liked_posts = db.paginate(query, page=page,
                            per_page=app.config['POSTS_PER_PAGE'],
                            error_out=False)
    next_url = url_for('likes', username=user.username, page=liked_posts.next_num) \
        if liked_posts.has_next else None
    prev_url = url_for('likes', username=user.username, page=liked_posts.prev_num) \
        if liked_posts.has_prev else None
    return render_template("likes.html", title='Likes', liked_posts=liked_posts.items, next_url=next_url, prev_url=prev_url, current_user=current_user, user=user)






@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        current_user.liked_posts = form.liked_posts.data
        if form.checkbox.data == True:
            current_user.profile_pic = None
            db.session.commit()
        else:
            pic = form.profile_pic.data
            if pic:
                pic_name = str(uuid.uuid1()) + "_" + secure_filename(pic.filename)
                pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
                current_user.profile_pic = pic_name
                db.session.commit()
            else:
                db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('profile', username=current_user.username))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
        form.profile_pic.data  = current_user.profile_pic 
        form.liked_posts.data = current_user.liked_posts
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)



@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    try: 
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
            if form.checkbox.data == True:
                post.post_pic = None
                db.session.commit()
            else:
                pic = form.post_pic.data
                if pic:
                    pic_name = str(uuid.uuid1()) + "_" + secure_filename(pic.filename)
                    pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
                    post.post_pic = pic_name
                    db.session.commit()
                else:
                    db.session.commit()
            flash('Your changes have been saved.')
            return redirect(url_for('post', id=post.id))
        return render_template('create_post.html', title='New Post', h='New Post',
                            form=form)
    except ElasticConnectionError:
        error="Connection error!"
        return render_template('error.html', error=error)
    except ConnectionTimeoutError:
        error="Connection Timeout error!"
        return render_template('error.html', error=error)



@app.template_filter("filter_replies")
def filter_replies(id):
    query = sa.select(Comment).where((Comment.parent_id==id))
    replies = db.session.scalars(query).all()
    return len(replies)



@app.route('/post/<id>', methods=['GET', 'POST'])
def post(id):
    post = db.first_or_404(sa.select(Post).where(Post.id == id))
    form = CommentForm()
    form2 = ReplyForm()
    if current_user.is_authenticated:
        authenticated = True
    else:
        authenticated = False
    if form.validate_on_submit():
        if not authenticated:
            error="Login to comment."
            return render_template('error.html', error=error)
        comment = Comment(body=form.comment.data, user_id=current_user.id, post_id=post.id)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('post', id=post.id))
    if form2.validate_on_submit():
        if not authenticated:
            error="Login to comment."
            return render_template('error.html', error=error)
        parent_id = form2.parent_id.data
        reply_to = None
        comment = db.first_or_404(sa.select(Comment).where(Comment.id == parent_id))
        if comment.parent_id:
            reply_to = comment.author.username
            parent_id = comment.parent_id
        comment = Comment(body=form2.reply.data, user_id=current_user.id, post_id=post.id, parent_id=parent_id, reply_to=reply_to)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('post', id=post.id))
    query = sa.select(Post).where((Post.media==1)&(Post.id!=post.id)).order_by(Post.timestamp.desc())
    posts_media1 = db.session.scalars(query).all()[:4]
    posts_media2 = db.session.scalars(query).all()[5:8]
    query = sa.select(Post).where((Post.news==1)&(Post.id!=post.id)).order_by(Post.timestamp.desc())
    posts_news1 = db.session.scalars(query).all()[:4]
    posts_news2 = db.session.scalars(query).all()[5:8]
    query = sa.select(Post).where((Post.sports==1)&(Post.id!=post.id)).order_by(Post.timestamp.desc())
    posts_sports1 = db.session.scalars(query).all()[:4]
    posts_sports2 = db.session.scalars(query).all()[5:8]
    query = sa.select(Post).where((Post.showbiz==1)&(Post.id!=post.id)).order_by(Post.timestamp.desc())
    posts_showbiz1 = db.session.scalars(query).all()[:4]
    posts_showbiz2 = db.session.scalars(query).all()[5:8]
    query = sa.select(Post).where((Post.viral==1)&(Post.id!=post.id)).order_by(Post.timestamp.desc())
    posts_viral1 = db.session.scalars(query).all()[:4]
    posts_viral2 = db.session.scalars(query).all()[5:8]
    filter_after = datetime.today() - timedelta(days = 120)
    query = sa.select(Post).join(Like).where(Post.id!=post.id).filter(Post.timestamp >= filter_after).group_by(Like.post_id).order_by(func.count(Like.post_id).desc()).order_by(Post.timestamp.desc())
    trending = db.session.scalars(query).all()[:6]
    page = request.args.get('page', 1, type=int)
    query = sa.select(Comment).where((Comment.post_id==post.id)&(Comment.parent_id==None)).order_by(Comment.num_likes.desc()).order_by(Comment.timestamp.desc())
    comments = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    query = sa.select(Comment).where((Comment.post_id==post.id)&(Comment.parent_id!=None)).order_by(Comment.timestamp)
    replies =  db.session.scalars(query).all()
    next_url = url_for('post', id=post.id, page=comments.next_num) \
        if comments.has_next else None
    prev_url = url_for('post', id=post.id, page=comments.prev_num) \
        if comments.has_prev else None
    return render_template('post.html', post=post, posts_media1=posts_media1, posts_media2=posts_media2, posts_news1=posts_news1, posts_news2=posts_news2, 
                            posts_sports1=posts_sports1, posts_sports2=posts_sports2, posts_showbiz1=posts_showbiz1, posts_showbiz2=posts_showbiz2,
                            posts_viral1=posts_viral1, posts_viral2=posts_viral2, current_user=current_user, trending=trending, comments=comments, replies=replies, 
                            form=form, form2=form2, authenticated=authenticated, next_url=next_url, prev_url=prev_url)


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
            if form.checkbox.data == True:
                post.post_pic = None
                db.session.commit()
            else:
                pic = form.post_pic.data
                if pic:
                    pic_name = str(uuid.uuid1()) + "_" + secure_filename(pic.filename)
                    pic.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
                    post.post_pic = pic_name
                    db.session.commit()
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


@app.route('/media')
def media():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).where(Post.media==1).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('media', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('media', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template("category.html", title='Media', category="Media", posts=posts.items, next_url=next_url, prev_url=prev_url, current_user=current_user)


@app.route('/news')
def news():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).where(Post.news==1).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('news', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('news', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template("category.html", title='News', category="News", posts=posts.items, next_url=next_url, prev_url=prev_url, current_user=current_user)


@app.route('/showbiz')
def showbiz():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).where(Post.showbiz==1).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('showbiz', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('showbiz', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template("category.html", title='Showbiz', category="Showbiz", posts=posts.items, next_url=next_url, prev_url=prev_url, current_user=current_user)


@app.route('/sports')
def sports():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).where(Post.sports==1).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('sports', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('sports', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template("category.html", title='Sports', category="Sports", posts=posts.items, next_url=next_url, prev_url=prev_url, current_user=current_user)


@app.route('/viral')
def viral():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).where(Post.viral==1).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('viral', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('viral', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template("category.html", title='Viral', category="Viral", posts=posts.items, next_url=next_url, prev_url=prev_url, current_user=current_user)


@app.route('/search')
def search():
    if not g.search_form.validate():
        return redirect(url_for('index'))
    page = request.args.get('page', 1, type=int)
    posts, total = Post.search(g.search_form.q.data, page, app.config['POSTS_PER_PAGE'])
    if total == -1:
        error="Connection error!"
        return render_template('error.html', error=error)
    else:
        next_url = url_for('main.search', q=g.search_form.q.data, page=page + 1) \
            if total > page * app.config['POSTS_PER_PAGE'] else None
        prev_url = url_for('main.search', q=g.search_form.q.data, page=page - 1) \
            if page > 1 else None
        return render_template('search.html', title='Search', posts=posts,
                                next_url=next_url, prev_url=prev_url, total=total, query=g.search_form.q.data, current_user=current_user)


@app.route('/like_post/<id>', methods=['POST'])
@login_required
def like_post(id):
    post = db.first_or_404(sa.select(Post).where(Post.id == id))
    query = sa.select(Like).where((Like.user_id==current_user.id)&(Like.post_id==post.id))
    like = db.session.scalars(query).first()
    if like:
        db.session.delete(like)
        query = sa.select(Notification).where((Notification.sender_id==current_user.id)&(Notification.recipient_id==post.user_id)&(Notification.post_id==post.id)&(Notification.category=="like_post"))
        notification = db.session.scalars(query).first()
        if notification:
            db.session.delete(notification)
    else:
        like = Like(user_id=current_user.id, post_id=post.id)
        notification = Notification(sender_id=current_user.id, recipient_id=post.user_id, post_id=post.id, category="like_post")
        db.session.add(like)
        db.session.add(notification)
    db.session.commit()
    post.author.add_notification_call('unread_notification_count', post.author.unread_notification_count())
    db.session.commit()
    return jsonify({"likes": len(post.likes), "liked": current_user.id in map(lambda x: x.user_id, post.likes)})


@app.route('/delete_comment/<id>', methods=['GET', 'POST'])
@login_required
def delete_comment(id):
    comment = db.first_or_404(sa.select(Comment).where(Comment.id == id))
    if comment.author == current_user:
        db.session.delete(comment)       
        db.session.commit()
        flash('Your comment has been deleted.')
        return redirect(url_for('post', id=comment.post_id))
    else:
        error="You cannot delete the comment of another user!"
        return render_template('error.html', error=error)


@app.route('/like_comment/<id>', methods=['POST'])
@login_required
def like_comment(id):
    comment = db.first_or_404(sa.select(Comment).where(Comment.id == id))
    query = sa.select(Like_Comment).where((Like_Comment.user_id==current_user.id)&(Like_Comment.comment_id==comment.id))
    like = db.session.scalars(query).first()
    if like:
        db.session.delete(like)
    else:
        like = Like_Comment(user_id=current_user.id, comment_id=comment.id)
        db.session.add(like)
    db.session.commit()
    comment.num_likes = len(comment.likes)
    db.session.commit()
    return jsonify({"likes": len(comment.likes), "liked": current_user.id in map(lambda x: x.user_id, comment.likes)})


@app.route('/notifications')
@login_required
def notifications():
    current_user.last_notification_read_time = datetime.now(timezone.utc)
    current_user.add_notification_call('unread_notification_count', 0)
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    query = current_user.notifications_received.select().order_by(
        Notification.timestamp.desc())
    notifications = db.paginate(query, page=page,
                           per_page=app.config['POSTS_PER_PAGE'],
                           error_out=False)
    next_url = url_for('notifications', page=notifications.next_num) \
        if notifications.has_next else None
    prev_url = url_for('notifications', page=notifications.prev_num) \
        if notifications.has_prev else None
    return render_template('notifications.html', notifications=notifications.items,
                           next_url=next_url, prev_url=prev_url)



@app.route('/notification_calls')
@login_required
def notification_calls():
    since = request.args.get('since', 0.0, type=float)
    query = current_user.notification_calls.select().where(
        Notification_Call.timestamp > since).order_by(Notification_Call.timestamp.asc())
    notification_calls = db.session.scalars(query)
    return [{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notification_calls]