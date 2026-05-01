"""Initialize database tables from SQLAlchemy models and create default admin user.

Usage:
    cd backend
    python scripts/init_db.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from app.database import engine, SessionLocal, Base
from app.models.models import User
from app.config import settings


def init_db():
    """Create all tables defined in ORM models."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

    # Initialize default admin account
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if admin is None:
            password_hash = bcrypt.hashpw(
                settings.ADMIN_INIT_PASSWORD.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")
            admin = User(
                username=settings.ADMIN_USERNAME,
                password_hash=password_hash,
            )
            db.add(admin)
            db.commit()
            print(f"Default admin account created: username='{settings.ADMIN_USERNAME}', password='{settings.ADMIN_INIT_PASSWORD}'")
        else:
            print(f"Admin account already exists: username='{settings.ADMIN_USERNAME}'")
    except Exception as e:
        print(f"Error creating admin account: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()