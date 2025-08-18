from datetime import datetime, timedelta, timezone
from flask import current_app, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from flask_babel import _
import sqlalchemy as sa
import csv

from app import db
from app.admin.forms import ApprovePostForm, CreateUserForm
from app.admin import bp
from app.main.forms import EmptyForm
from app.models import Comment, Post, User

def admin_or_analyst_required():
    if current_user.is_admin() or current_user.is_analyst():
        return None
    flash(_('You do not have permission to access this page.'))
    return redirect(url_for('main.index'))

@bp.route('/admin/all_posts')
@login_required
def all_posts():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')

    posts_query = sa.select(Post).order_by(Post.timestamp.desc())

    if status ==  'approved':
        posts_query = posts_query.where(Post.is_approved.is_(True))
    elif status == 'pending':
        posts_query = posts_query.where(Post.is_approved.is_(False))

    posts = db.paginate(posts_query, page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    form = EmptyForm()
    
    next_url = url_for('admin.all_posts', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('admin.all_posts', page=posts.prev_num) if posts.has_prev else None
    
    return render_template(
        'admin/all_posts.html',
        title='All Posts',
        posts=posts,
        next_url=next_url,
        prev_url=prev_url,
        form=form,
        status=status
    )

@bp.route('/admin/all_users')
@login_required
def all_users():
    if not current_user.is_admin():
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    filter_username = request.args.get('page', '', type=str).strip()
    filter_role = request.args.get('role', '', type=str).strip()

    users_query = sa.select(User)
    if filter_username:
        users_query = users_query.where(User.username.ilike(f"%{filter_username}%"))
    if filter_role:
        users_query = users_query.where(User.role == filter_role)

    users_query = users_query.order_by(User.username.asc())

    users = db.paginate(users_query, page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    
    next_url = url_for('admin.all_users', page=users.next_num) if users.has_next else None
    prev_url = url_for('admin.all_users', page=users.prev_num) if users.has_prev else None
 
    return render_template(
        'admin/all_users.html',
        title='All Users',
        users=users,
        next_url=next_url,
        prev_url=prev_url
    )

@bp.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.is_analyst():
        return redirect(url_for('admin.report'))
    elif current_user.is_user():
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

    total_users = db.session.scalar(sa.select(sa.func.count()).select_from(User))

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    active_today = db.session.scalar(
    sa.select(sa.func.count()).select_from(User).where(User.last_seen >= yesterday)
    )

    return render_template(
        'admin/admin_dashboard.html',
        title='Admin Dashboard',
        posts=pending_posts,
        form=form,
        next_url=next_url,
        prev_url=prev_url,
        total_users=total_users,
        active_today=active_today
    )

@bp.route('/admin/approve_post/<int:post_id>', methods=['POST'])
@login_required
def approve_post(post_id):
    if not current_user.is_admin():
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
    if not current_user.is_admin():
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
    if not current_user.is_admin():
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
    if not current_user.is_admin():
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

@bp.route('/admin/report')
@login_required
def report():
    resp = admin_or_analyst_required()
    if resp:
        return resp
    
    filter_status = request.args.get('status', 'all')
    filter_user = request.args.get('user', '')
    order = request.args.get('order', 'timestamp_desc')

    query = sa.select(Post)

    if filter_status == 'approved':
        query = query.where(Post.is_approved.is_(True))
    elif filter_status == 'pending':
        query = query.where(Post.is_approved.is_(False))

    if filter_user:
        query = query.join(User).where(User.username.ilike(f"%{filter_user}%"))

    if order == 'timestamp_asc':
        query = query.order_by(Post.timestamp.asc())
    elif order == 'title_asc':
        query = query.order_by(Post.title.asc())
    elif order == 'title_desc':
        query = query.order_by(Post.title.desc())
    else:  # default
        query = query.order_by(Post.timestamp.desc())

    query = query.order_by(Post.timestamp.desc())
    posts = db.session.scalars(query).all()

    metrics = {
        'total_posts': db.session.scalar(sa.select(sa.func.count(Post.id))),
        'pending_posts': db.session.scalar(sa.select(sa.func.count(Post.id)).where(Post.is_approved.is_(False))),
        'total_users': db.session.scalar(sa.select(sa.func.count(User.id))),
        'posts_with_images': db.session.scalar(sa.select(sa.func.count(Post.id)).where(Post.image.isnot(None))),
    }

    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['POSTS_PER_PAGE']
    start = (page - 1) * per_page
    end = start + per_page
    paginated_posts = posts[start:end]

    next_url = url_for('admin.report', page=page + 1, status=filter_status, user=filter_user) if end < len(posts) else None
    prev_url = url_for('admin.report', page=page - 1, status=filter_status, user=filter_user) if page > 1 else None

    return render_template('admin/report.html',
                           posts=paginated_posts,
                           metrics=metrics,
                           filter_status=filter_status,
                           filter_user=filter_user,
                           next_url=next_url,
                           prev_url=prev_url)

from io import StringIO

@bp.route('/admin/report/export')
@login_required
def export_report():
    resp = admin_or_analyst_required()
    if resp:
        return resp

    # Get filters from request
    filter_status = request.args.get('status', 'all')
    filter_user = request.args.get('user', '')
    order = request.args.get('order', 'timestamp_desc')

    # Build query
    query = sa.select(Post)

    if filter_status == 'approved':
        query = query.where(Post.is_approved.is_(True))
    elif filter_status == 'pending':
        query = query.where(Post.is_approved.is_(False))

    if filter_user:
        query = query.join(User).where(User.username.ilike(f"%{filter_user}%"))

    # Apply ordering
    if order == 'timestamp_asc':
        query = query.order_by(Post.timestamp.asc())
    elif order == 'timestamp_desc':
        query = query.order_by(Post.timestamp.desc())
    elif order == 'title_asc':
        query = query.order_by(Post.title.asc())
    elif order == 'title_desc':
        query = query.order_by(Post.title.desc())

    posts = db.session.scalars(query).all()

    # Generate CSV
    def generate():
        output = []
        header = ['Post ID', 'Title', 'Author', 'Status', 'Comments', 'Timestamp']
        output.append(','.join(header))
        for post in posts:
            row = [
                str(post.id),
                post.title.replace(',', ' '),
                post.author.username,
                'Approved' if post.is_approved else 'Pending',
                str(post.comment_count()),
                post.timestamp.isoformat()
            ]
            output.append(','.join(row))
        return '\n'.join(output)

    csv_file = Response(generate(), mimetype='text/csv')
    csv_file.headers["Content-Disposition"] = "attachment; filename=platform_report.csv"
    return csv_file

@bp.route('/admin/analytics')
@login_required
def analytics():
    resp = admin_or_analyst_required()
    if resp:
        return resp
    
    # Posts Over Time
    posts_query = sa.select(Post).order_by(Post.timestamp.asc())
    posts = db.session.scalars(posts_query).all()

    # Aggregrate Posts Per Day
    posts_per_day = {}
    approved_per_day = {}
    for post in posts:
        day = post.timestamp.date()
        posts_per_day[day] = posts_per_day.get(day, 0) + 1
        if post.is_approved:
            approved_per_day[day] = approved_per_day.get(day, 0) + 1

    pending_per_day = {}
    for post in posts:
        day = post.timestamp.date()
        if not post.is_approved:
            pending_per_day[day] = pending_per_day.get(day, 0) + 1

    # Active users per day based on last_seen
    users_query = sa.select(User).order_by(User.last_seen.asc())
    users = db.session.scalars(users_query).all()

    active_users_per_day = {}
    for user in users:
        if user.last_seen:
            day = user.last_seen.date()
            active_users_per_day[day] = active_users_per_day.get(day, 0) + 1

    # Top Posters
    top_users_query = sa.select(User.username, sa.func.count(Post.id).label('post_count')) \
                        .join(Post) \
                        .group_by(User.id) \
                        .order_by(sa.desc("post_count")) \
                        .limit(5)
    top_users = db.session.execute(top_users_query).all()

    return render_template(
        'admin/analytics.html',
        posts_per_day=posts_per_day,
        approved_per_day=approved_per_day,
        pending_per_day=pending_per_day,
        active_users_per_day=active_users_per_day,
        top_users=top_users
    )

@bp.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_admin():
        flash('Permission denied.')
        return redirect(url_for('main.index'))
    
    form = CreateUserForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'User {user.username} created successfully.')
        return redirect(url_for('admin.all_users'))
    
    return render_template('admin/create_user.html', form=form, title='Create User')

@bp.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin():
        flash('Permission denied.')
        return redirect(url_for('main.index'))

    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.')
        return redirect(url_for('admin.all_users'))

    # Protect the "original admin" (first admin)
    first_admin = db.session.scalar(sa.select(User).where(User.role=='admin').order_by(User.id.asc()))
    if user.id == first_admin.id:
        flash('Cannot delete the original admin.')
        return redirect(url_for('admin.all_users'))
    elif user.id == current_user.id:
        flash('You cannot delete yourself.')
        return redirect(url_for('admin.all_users'))

    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} deleted.')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting user.')
    return redirect(url_for('admin.all_users'))
