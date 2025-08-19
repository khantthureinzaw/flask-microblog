from datetime import datetime, timezone
from flask import render_template, flash, redirect, url_for, request, g, \
    current_app
from flask_login import current_user, login_required
from flask_babel import _, get_locale
import sqlalchemy as sa
from langdetect import detect, LangDetectException
from app import db
from app.admin.forms import DeletePostForm
from app.main.forms import CommentForm, EditProfileForm, EmptyForm, PostForm, SearchForm
from app.models import Comment, User, Post
from app.translate import translate
from app.main import bp

import uuid
import os
from werkzeug.utils import secure_filename


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
    g.locale = str(get_locale())


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():

    # Upload posts
    form = PostForm()
    if form.validate_on_submit():
        post = Post(
            title=form.title.data, 
            body=form.post.data, 
            author=current_user, 
            is_approved=True if current_user.is_admin() else False)
        
        file = form.image.data
        if file:
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
            post.image = filename

        db.session.add(post)
        db.session.commit()
        if current_user.is_admin():
            flash(_('Your post is now live!'))
        else:
            flash(_('Your post is awaiting approval!'))
        return redirect(url_for('main.index'))
    
    # Show posts
    page = request.args.get('page', 1, type=int)
    posts = db.paginate(current_user.following_posts(), page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.index', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.index', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title='Home', posts=posts, form=form, next_url=next_url, prev_url=prev_url)

@bp.route('/post/<post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = db.first_or_404(sa.select(Post).where(
        Post.id == post_id
    ))
    form = CommentForm()
    delete_post = DeletePostForm()

    # Show Comments
    page = request.args.get('page', 1, type=int)
    comments = db.paginate(post.get_comments(), page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.post_detail', page=comments.next_num) if comments.has_next else None
    prev_url = url_for('main.post_detail', page=comments.prev_num) if comments.has_prev else None
    return render_template('post_detail.html', title=post.title, post=post, form=form, delete_post=delete_post, comments=comments, next_url=next_url, prev_url=prev_url)

@bp.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = db.first_or_404(sa.select(Post).where(Post.id == post_id))
    
    # Only allow the author to edit
    if post.author != current_user:
        flash(_("You cannot edit someone else's post."))
        return redirect(url_for('main.post_detail', post_id=post_id))
    
    form = PostForm()
    
    if request.method == 'GET':
        form.title.data = post.title
        form.post.data = post.body

    if form.validate_on_submit():
        post.title = form.title.data
        post.body = form.post.data
        
        file = form.image.data
        if file:
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
            post.image = filename
        
        db.session.commit()
        flash(_("Your post has been updated."))
        return redirect(url_for('main.post_detail', post_id=post_id))
    
    return render_template('edit_post.html', title=_("Edit Post"), form=form, post=post)

@bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = db.first_or_404(sa.select(Post).where(Post.id == post_id))
    
    # Only allow the author to delete
    if post.author != current_user:
        flash(_("You cannot delete someone else's post."))
        return redirect(url_for('main.post_detail', post_id=post_id))
    
    if post.image:
        try:
            os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], post.image))
        except FileNotFoundError:
            pass
    
    db.session.delete(post)
    db.session.commit()
    flash(_("Your post has been deleted."))
    return redirect(url_for('main.index'))



@bp.route('/post/<post_id>/comment', methods=['GET', 'POST'])
@login_required
def make_comment(post_id):
    post = db.first_or_404(sa.select(Post).where(
        Post.id == post_id
    ))
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data, author=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        flash(_('You comment is now live!'))
        return redirect(url_for('main.post_detail', post_id=post_id))
    return render_template('post_detail.html', title=post.title, post=post, form=form)

@bp.route('/explore')
def explore():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).where(Post.is_approved.is_(True)).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title='Explore', posts=posts, next_url=next_url, prev_url=prev_url)


@bp.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(
        User.username == username
    ))
    page = request.args.get('page', 1, type=int)

    # Approved posts
    approved_query = user.posts.select().where(Post.is_approved.is_(True)).order_by(Post.timestamp.desc())
    approved_posts = db.paginate(approved_query, page=page,
                        per_page=3,
                        error_out=False)
    next_url = url_for('main.user', username=user.username, page=approved_posts.next_num) \
        if approved_posts.has_next else None
    prev_url = url_for('main.user', username=user.username, page=approved_posts.prev_num) \
        if approved_posts.has_prev else None
    
    # Pending posts (only if the user is viewing their own profile)
    pending_posts = None
    p_next_url = None
    p_prev_url = None
    p_page = request.args.get('p_page', 1, type=int)
    if user == current_user:
        pending_query = user.posts.select().where(Post.is_approved.is_(False)).order_by(Post.timestamp.desc())
        pending_posts = db.paginate(pending_query, page=p_page, 
                                    per_page=3,
                                    error_out=False)
        p_next_url = url_for('main.user', username=user.username, p_page=pending_posts.next_num) \
            if pending_posts.has_next else None
        p_prev_url = url_for('main.user', username=user.username, p_page=pending_posts.prev_num) \
            if pending_posts.has_prev else None
    

    form = EmptyForm()
    return render_template('user.html', user=user, posts=approved_posts, pending_posts=pending_posts, form=form, next_url=next_url, prev_url=prev_url, p_next_url=p_next_url, p_prev_url=p_prev_url)

@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me

    return render_template('edit_profile.html', title='Edit Profile', form=form)


@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(_('User %(username)s not found.', username=username))
            return redirect(url_for('main.index'))
        if user == current_user:
            flash(_('You cannot follow yourself!'))
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(_('You are following %(username)s!', username=username))
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(_('User %(username)s not found.', username=username))
            return redirect(url_for('main.index'))
        if user == current_user:
            flash(_('You cannot unfollow yourself!'))
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(_('You are not following %(username)s.', username=username))
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))
    
@bp.route('/search')
def search():
    form = SearchForm(request.args)
    query = form.query.data
    page = request.args.get('page', 1, type=int)
    
    post_query = sa.select(Post).where(
        sa.and_(
            Post.is_approved.is_(True),
            sa.or_(
                Post.title.ilike(f'%{query}%'),
                Post.body.ilike(f'%{query}%')
            )
        )
    ).order_by(Post.timestamp.desc())

    posts = db.paginate(
        post_query,
        page=page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )

    next_url = url_for('main.search', query=query, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.search', query=query, page=posts.prev_num) if posts.has_prev else None

    return render_template(
        'search_results.html',
        posts=posts.items,
        query=query,
        next_url=next_url,
        prev_url=prev_url,
        form=form
    )


@bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    data = request.get_json()
    return {'text': translate(data['text'],
                              data['source_language'],
                              data['dest_language'])}