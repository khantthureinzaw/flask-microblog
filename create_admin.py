from app import create_app, db
from app.models import User

def create_admin():
    app = create_app()
    admin = User.query.filter_by(username="admin").first()
    if admin:
        print("Admin user already exists.")
        return
    
    admin = User(
        username='admin',
        email='admin@example.com',
        role='admin'
    )

    admin.set_password('admin')
    db.session.add(admin)
    db.session.commit()
    print("Default admin created: username=admin, password=admin")

if __name__ == "__main__":
    create_admin()