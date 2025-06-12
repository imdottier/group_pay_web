from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import Annotated
from datetime import timedelta
from backend.dependencies import get_current_user
import logging

from jose import jwt, JWTError

from backend.crud import (
    get_user_by_email, get_user_by_username,
    get_user_by_user_id, create_user, authenticate_user
) 
from backend.schemas import User, UserCreate, Token, TokenData
from backend.security import (
    create_access_token,
    oauth2_scheme, 
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
)
from backend.database import DbSessionDep

logger = logging.getLogger(__name__) 

router = APIRouter(
    tags=["Authentication"]
)


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: DbSessionDep):
    db_user_email = await get_user_by_email(db, email=user_in.email)
    if db_user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    db_user_username = await get_user_by_username(db, username=user_in.username)
    if db_user_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )
    try:
        # Attempt to create the user
        new_user = await create_user(db=db, user=user_in)
        logger.info(f"User registered: {new_user.username}")
        return new_user

    except IntegrityError as e:
        logger.warning(f"Registration conflict/IntegrityError: {e}")

        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after registration IntegrityError: {rollback_err}")

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered.", # Covers the most common case
        ) from e

    except Exception as e:
        # Catch ANY other unexpected error during create_user or elsewhere
        logger.exception("Unexpected error during user registration.") # Log the full error
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after login exception: {rollback_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during registration.", # Generic message
        ) from e


@router.post("/login/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSessionDep,
):
    """Logs in a user and returns an access token."""
    try:
        logger.info(f"Login attempt for user: {form_data.username}")
        # --- Core Logic ---
        user = await authenticate_user(
            db=db,
            identifier=form_data.username, # Handles email OR username
            password=form_data.password
        )

        if user is None:
            logger.warning(f"Failed login attempt for user: {form_data.username}")
            # This handles the expected "authentication failed" case correctly
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # --- If authentication succeeded ---
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        # Ensure user_id is available on your user model returned by authenticate_user
        access_token = create_access_token(
            data={"sub": str(user.user_id)}, expires_delta=access_token_expires
        )
        logger.info(f"Successful login for user: {form_data.username}")
        return Token(access_token=access_token, token_type="bearer")
        # --- End Core Logic ---

    except HTTPException:
        raise

    except Exception as e:
        # Catch ANY unexpected error during authentication or token creation
        logger.exception(f"Unexpected error during login for {form_data.username}.") # Log the full error
        
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after login exception: {rollback_err}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during login.", # Generic message
        ) from e