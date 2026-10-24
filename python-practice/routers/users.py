
from sqlite3 import IntegrityError
from fastapi.security import OAuth2PasswordRequestForm
from typing_extensions import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from database import SessionDep
from errors import ErrorDetail
from models.users import UserRead, UserCreate, User

from auth import create_access_token, hash_password, verify_password

from sqlmodel import select

router = APIRouter()

@router.post("/users", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, session: SessionDep):
    """Create a new user."""
    hashed_password = hash_password(payload.password)
    user = User(username=payload.username, hashed_password=hashed_password)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ErrorDetail.USERNAME_TAKEN)
    session.refresh(user)
    return user

@router.post("/token")
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    """Authenticate a user and return a token."""
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"}, detail=ErrorDetail.INVALID_LOGIN)

    token = create_access_token(user.username)
    # For simplicity, we'll return the username as the token. In a real application, you would generate a JWT.
    return {"access_token": token, "token_type": "bearer"}