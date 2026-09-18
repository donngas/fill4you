from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounts.models import User


def get_user(db: Session, user_id: int | None) -> User | None:
    return db.get(User, user_id) if user_id else None


def upsert_google_user(
    db: Session,
    *,
    subject: str,
    email: str,
    display_name: str,
    picture_url: str | None,
) -> User:
    user = db.scalar(select(User).where(User.google_subject == subject))
    if user is None:
        user = User(
            google_subject=subject,
            email=email,
            display_name=display_name or email,
            picture_url=picture_url,
        )
        db.add(user)
    else:
        user.email = email
        user.display_name = display_name or email
        user.picture_url = picture_url
    db.commit()
    db.refresh(user)
    return user


def get_or_create_development_user(db: Session) -> User:
    email = "developer@fill4you.local"
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            display_name="Development User",
            google_subject=None,
            picture_url=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
