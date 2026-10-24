
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from datetime import datetime, timedelta, timezone

from sqlmodel import select
from settings import settings
import jwt

from typing import Annotated
from fastapi import Depends, HTTPException, status
from database import SessionDep

from errors import ErrorDetail

from models.users import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    """Hash a password for storing in the database."""
    return password_hash.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hashed password."""
    return password_hash.verify(password, hashed_password)

def create_access_token(username: str) -> str:
    """Create a simple access token for the given username."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": username, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep):
    """Get the current user from the token."""
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"}, detail=ErrorDetail.INVALID_TOKEN)
    try:
        # decode() checks the signature AND the `exp` claim. InvalidTokenError
        # is the base class for bad signatures, expired tokens, and garbage input.
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.InvalidTokenError:
        raise credentials_error
    username = payload.get("sub")
    if username is None:
        raise credentials_error
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise credentials_error
    return user

CurrentUserDep = Annotated[User, Depends(get_current_user)]