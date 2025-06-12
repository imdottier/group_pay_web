from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import logging

from backend.crud import (
    get_notifications_for_user, get_notification_by_id_for_user,
    mark_notification_as_read, mark_all_notifications_as_read, get_unread_notification_count
)

import backend.schemas as schemas
import backend.models as models
from backend.database import DbSessionDep
from backend.dependencies import (
    get_current_user,
)
from backend.services import payment_services

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    responses={401: {"description": "Not authenticated"}} # Default for this router
)

@router.get("/me", response_model=List[schemas.Notification])
async def read_my_notifications(
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of notifications to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of notifications to return"),
    unread_only: bool = Query(False, description="Filter by unread notifications only")
):
    """
    Retrieve notifications for the current authenticated user.
    """
    logger.info(f"User {current_user.user_id} fetching their notifications (unread_only: {unread_only}).")
    try:
        notifications = await get_notifications_for_user(
            db=db, 
            user_id=current_user.user_id, 
            skip=skip, 
            limit=limit, 
            unread_only=unread_only
        )
        
        return notifications
    
    except Exception as e:
        logger.exception(f"Error fetching notifications for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve notifications."
        ) from e


@router.post(
    "/{notification_id}/read",
    response_model=schemas.Notification, # Return the updated notification
    summary="Mark a notification as read"
)
async def mark_notification_as_read_endpoint(
    notification_id: int,
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
):
    """
    Mark a specific notification as read for the current user.
    """
    logger.info(f"User {current_user.user_id} attempting to mark notification {notification_id} as read.")
    
    try:
        # Get the notification
        db_notification = await get_notification_by_id_for_user(
            db=db, notification_id=notification_id, user_id=current_user.user_id
        )
        if not db_notification:
            logger.warning(
                f"User {current_user.user_id} tried to mark non-existent or unauthorized notification {notification_id} as read."
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found or not yours.")

        # Mark as read
        if db_notification.is_read:
            logger.info(f"Notification {notification_id} was already read by user {current_user.user_id}.")
            return db_notification # Return as is, no change needed

        updated_notification = await mark_notification_as_read(
            db=db, db_notification=db_notification
        )
        
        logger.info(f"User {current_user.user_id} successfully marked notification {notification_id} as read.")
        return updated_notification

    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(
            f"Error marking notification {notification_id} as read for user {current_user.user_id}: {e}"
        )
        # CRUD should handle rollback for db.commit errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not mark notification as read."
        ) from e
    

@router.post(
    "/mark-all-as-read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all notifications as read"
)
async def mark_all_my_notifications_as_read(
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
):
    logger.info(f"User {current_user.user_id} attempting to mark all their notifications as read.")
    try:
        updated_count = await mark_all_notifications_as_read(
            db=db, user_id=current_user.user_id
        )
        logger.info(f"User {current_user.user_id} marked {updated_count} notifications as read.")

    except Exception as e:
        logger.exception(f"Error marking all notifications as read for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not mark all notifications as read."
        ) from e
    

@router.get(
    "/me/unread-count",
    response_model=schemas.UnreadNotificationCount,
    summary="Get count of unread notifications"
)
async def get_my_unread_notification_count(
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
):
    logger.debug(f"User {current_user.user_id} fetching unread notification count.")
    try:
        count = await get_unread_notification_count(
            db=db, user_id=current_user.user_id
        )
        return schemas.UnreadNotificationCount(unread_count=count)
    
    except Exception as e:
        logger.exception(f"Error fetching unread notification count for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve unread notification count."
        ) from e