from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
import logging

import backend.schemas as schemas
import backend.models as models
from .auth import get_current_user

from backend.crud import (
    update_user,
    search_users,
    get_user_by_user_id,
    update_user_profile_image,
    get_user_by_username,
)
from backend.schemas import User
from backend.dependencies import get_current_user
from backend.database import DbSessionDep
from backend.services.storage_service import upload_file_to_gcs

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.get("/me", response_model=schemas.User)
async def read_users_me(
    current_user: User = Depends(get_current_user)
):
    return current_user


@router.get("/search", response_model=list[schemas.User])
async def search_for_users(
    query: str,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user)
):
    """
    Search for users by username or email.
    """
    if not query:
        return []
    
    users = await search_users(db, query=query, current_user_id=current_user.user_id)
    return users


@router.put("/me", response_model=schemas.User)
async def update_current_user_profile(
    user_update_data: schemas.UserUpdate,
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
):
    """
    Update current authenticated user's profile (username, full_name).
    """
    logger.info(f"User {current_user.user_id} attempting to update their profile with data: {user_update_data.model_dump(exclude_unset=True)}")

    update_data = user_update_data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided.",
        )

    # Check for duplicate username before attempting to update
    new_username = update_data.get("username")
    if new_username and new_username != current_user.username:
        existing_user = await get_user_by_username(db, username=new_username)
        if existing_user:
            logger.error(f"Username {new_username} already taken")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

    try:
        updated_user = await update_user(
            db=db, db_user=current_user, user_in=user_update_data
        )
        await db.commit()
        await db.refresh(updated_user)
        logger.info(f"User {updated_user.user_id} successfully updated their profile.")
        return updated_user

    except IntegrityError:
        # This will now primarily catch other potential integrity issues,
        # though the duplicate username case is handled above.
        await db.rollback()
        logger.warning(f"IntegrityError on profile update for user {current_user.user_id}.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A database conflict occurred. Please try again.",
        )
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error updating profile for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the profile.",
        ) from e


@router.put("/me/profile-image", response_model=User)
async def update_profile_image(
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
    profile_image: UploadFile = File(...),
):
    """
    Updates the current user's profile image.
    Receives an image file, uploads it to GCS, and updates the user's
    profile_image_url with the public URL of the uploaded image.
    """
    logger.info(f"User {current_user.user_id} attempting to update profile image.")
    
    # Basic validation for file type could be added here if desired
    # For example, check profile_image.content_type

    try:
        # Upload the file to Google Cloud Storage
        public_url = await upload_file_to_gcs(file=profile_image)

        # Update the user's profile_image_url in the database
        updated_user = await update_user_profile_image(
            db=db, user_id=current_user.user_id, image_url=public_url
        )

        await db.commit()
        await db.refresh(updated_user)

        logger.info(f"User {current_user.user_id} successfully updated profile image.")
        return updated_user

    except HTTPException:
        # Re-raise HTTPExceptions from the storage service
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(f"An unexpected error occurred while updating profile image for user {current_user.user_id}.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred."
        ) from e


@router.get("/{user_id}", response_model=schemas.User)
async def get_user_profile(
    user_id: int,
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user) # Ensures endpoint is protected
):
    """Get a specific user's public profile."""
    user = await get_user_by_user_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user