"""Auth router - login, create-user, me"""

from datetime import datetime, timedelta
from typing import List

import bcrypt

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import User

router = APIRouter()

# JWT bearer token extractor
security = HTTPBearer()


# ---------- Pydantic schemas ----------


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    admin_password: str  # Admin password required to create users


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserListResponse(BaseModel):
    users: List[UserResponse]


# ---------- Helper functions ----------


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: int, username: str) -> str:
    """Create a JWT access token with expiration."""
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ---------- Dependency injection ----------


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency that extracts and validates the current user from the JWT token.

    Use this dependency in any router that needs user authentication and data isolation.
    Example:
        @router.get("/my-data")
        async def my_data(current_user: User = Depends(get_current_user)):
            # Only access current_user.id data
    """
    payload = decode_access_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# ---------- API endpoints ----------


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """User login. Returns JWT token on success."""
    user = db.query(User).filter(User.username == request.username).first()
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        username=user.username,
        user_id=user.id,
    )


@router.post("/create-user", response_model=UserResponse)
async def create_user(request: CreateUserRequest, db: Session = Depends(get_db)):
    """Admin-only endpoint to create a new user account.

    Requires the admin password (configured via ADMIN_PASSWORD env variable)
    to prevent unauthorized account creation.
    """
    # Validate admin password
    if request.admin_password != settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect admin password",
        )

    # Check if username already exists
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Create user with hashed password
    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current logged-in user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        created_at=current_user.created_at,
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change password for the currently logged-in user.

    Requires the current password for verification.
    """
    # Verify old password
    if not verify_password(request.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码不正确",
        )

    # Validate new password
    if len(request.new_password) < 4 or len(request.new_password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码长度需在 4-128 个字符之间",
        )

    # Prevent same password
    if verify_password(request.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同",
        )

    # Update password
    current_user.password_hash = hash_password(request.new_password)
    db.commit()

    return {"message": "密码修改成功"}


@router.get("/users", response_model=UserListResponse)
async def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all user accounts. Requires authentication."""
    users = db.query(User).order_by(User.id).all()
    return UserListResponse(
        users=[
            UserResponse(id=u.id, username=u.username, created_at=u.created_at)
            for u in users
        ]
    )