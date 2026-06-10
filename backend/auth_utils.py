from datetime import datetime, timedelta
import os
from typing import Optional
import secrets
import hashlib

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import pbkdf2_sha256

import models, schemas
from database import get_db

SECRET_KEY = "Secret"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8
EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES = int(os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES", "1440"))
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("$2"):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except ValueError:
            return False
    try:
        return pbkdf2_sha256.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def is_bcrypt_hash(hashed_password: str) -> bool:
    return bool(hashed_password) and hashed_password.startswith("$2")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    # Ensure subject is a string as required by JWT spec
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), db=Depends(get_db)
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # jose may return all claims as strings; ensure we compare using integer ID
        user_id = int(user_id_raw)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.users.find_one({"id": user_id})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*roles: str):
    async def role_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        role = current_user.get("role")
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_dependency


def create_email_token(token_type: str) -> tuple[str, str]:
    """
    Create a secure token for email verification or password reset.
    Returns (raw_token, hashed_token).
    """
    raw_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, hashed_token


def verify_email_token(provided_token: str, stored_hash: str) -> bool:
    """Verify an email token by comparing hashes."""
    if not provided_token or not stored_hash:
        return False
    provided_hash = hashlib.sha256(provided_token.encode()).hexdigest()
    return provided_hash == stored_hash
