from flask import current_app, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_babel import _
import sqlalchemy as sa
from app import db
from app.admin.forms import ApprovePostForm
from app.admin import bp
from app.models import Comment, Post

@bp.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if not getattr(current_user, 'is_admin', False):
        flash(_('You do not have permission to access this page.'))
        return redirect(url_for('main.index'))
    
    form = ApprovePostForm()
    page = request.args.get('page', 1, type=int)

    # Pending Posts (not approved)
    pending_posts_query = sa.select(Post).where(Post.is_approved.is_(False)).order_by(Post.timestamp.desc())
    pending_posts = db.paginate(
        pending_posts_query,
        page = page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )
    next_url = url_for('admin.admin_dashboard', page=pending_posts.next_num) if pending_posts.has_next else None
    prev_url = url_for('admin.admin_dashboard', page=pending_posts.prev_num) if pending_posts.has_prev else None

    return render_template(
        'admin/admin_dashboard.html',
        title='Admin Dashboard',
        posts=pending_posts,
        form=form,
        next_url=next_url,
        prev_url=prev_url
    )

@bp.route('/admin/approve_post/<int:post_id>', methods=['POST'])
@login_required
def approve_post(post_id):
    if not getattr(current_user, 'is_admin', False):
        flash(_('You do not have permission to access this page.'))
        return redirect(url_for('main.index'))
    
    post = db.session.get(Post, post_id)
    if post:
        post.is_approved = True
        db.session.commit()
        flash(_('Post Approved'))
    return redirect(url_for('admin.admin_dashboard'))

@bp.route('/admin/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    if not getattr(current_user, 'is_admin', False):
        flash(_('You do not have permission to access this page.'))
        return redirect(url_for('main.index'))
    
    post = db.session.get(Post, post_id)
    if post:
        db.session.delete(post)
        db.session.commit()
        flash(_('Post Deleted'))

    next_page = request.form.get('next')
    if next_page:
        return redirect(next_page)
    return redirect(url_for('main.index'))

@bp.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    if not getattr(current_user, 'is_admin', False):
        flash(_('You do not have permission to access this page.'))
        return redirect(url_for('main.index'))
    
    comment = db.session.get(Comment, comment_id)
    if comment:
        db.session.delete(comment)
        db.session.commit()
        flash(_('Comment Deleted'))

    next_page = request.form.get('next')
    if next_page:
        return redirect(next_page)
    return redirect(url_for('main.index'))

@bp.route('/admin/post/<post_id>', methods=['GET', 'POST'])
@login_required
def admin_post_detail(post_id):
    if not getattr(current_user, 'is_admin', False):
        flash(_('You do not have permission to access this page.'))
        return redirect(url_for('main.index'))
    
    post = db.first_or_404(sa.select(Post).where(
        Post.id == post_id
    ))
    form = ApprovePostForm()
    return render_template(
        'admin/admin_post_detail.html',
        title=f'Approve {post.title}',
        post=post,
        form=form
    )