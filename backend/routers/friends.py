from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.exc import IntegrityError
import logging

from backend import crud, schemas
from backend.database import DbSessionDep
from backend.dependencies import get_current_user
from backend.models import NotificationType

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/friends",
    tags=["friends"],
    responses={401: {"description": "Not authenticated"}},
)

@router.post("/request", response_model=schemas.Friendship, status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    friend_request: schemas.FriendshipCreate,
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Send a friend request to another user."""
    requester_id = current_user.user_id
    addressee_id = friend_request.addressee_id
    logger.info(f"User {requester_id} attempting to send friend request to user {addressee_id}")

    # Check if the target user exists
    addressee_user = await crud.get_user_by_user_id(db, user_id=addressee_id)
    if not addressee_user:
        logger.warning(f"Friend request failed: User {requester_id} tried to add non-existent user {addressee_id}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to add not found.")

    # Use the new validation function from crud
    can_send = await crud.can_send_friend_request(db, user_id_1=requester_id, user_id_2=addressee_id)
    if not can_send:
        detail="You are already friends with this user or a request is pending."
        logger.warning(f"Friend request failed: User {requester_id} to {addressee_id}. Reason: {detail}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=detail
        )

    try:
        new_friendship = await crud.create_friendship(db, friendship_in=friend_request, requester_id=requester_id)

        # --- Create Notification for the Recipient ---
        await crud.create_notification(
            db=db,
            recipient_user_id=addressee_id,
            notification_type=NotificationType.friend_request,
            message=f"{current_user.full_name or current_user.username} sent you a friend request.",
            related_user_id=requester_id
        )
        # --- End Notification ---

        await db.commit()
        
        # Re-fetch the object to ensure all relationships are loaded for the response
        final_friendship = await crud.get_friendship_by_users(db, user_id_1=requester_id, user_id_2=addressee_id)
        
        logger.info(f"User {requester_id} successfully sent friend request to {addressee_id}.")
        return final_friendship
    except ValueError as e: # Catch self-friendship from crud
        logger.warning(f"Friend request failed: User {requester_id} tried to send a request to themselves. Error: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Error sending friend request from {requester_id} to {addressee_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not send friend request.")


@router.get("/", response_model=list[schemas.Friendship])
async def get_friends(
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Get a list of accepted friends."""
    logger.info(f"User {current_user.user_id} fetching their friend list.")
    try:
        friends = await crud.get_friendships_for_user(db, user_id=current_user.user_id)
        logger.info(f"Successfully fetched {len(friends)} friends for user {current_user.user_id}.")
        return friends
    except Exception as e:
        logger.exception(f"Error fetching friends for user {current_user.user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve friends.")


@router.get("/pending/received", response_model=list[schemas.Friendship])
async def get_received_pending_requests(
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Get a list of pending friend requests received by the user."""
    logger.info(f"User {current_user.user_id} fetching their received pending friend requests.")
    try:
        pending_requests = await crud.get_received_pending_friend_requests(db, user_id=current_user.user_id)
        logger.info(f"Successfully fetched {len(pending_requests)} received pending requests for user {current_user.user_id}.")
        return pending_requests
    except Exception as e:
        logger.exception(f"Error fetching received pending requests for user {current_user.user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve received pending requests.")


@router.get("/pending/sent", response_model=list[schemas.Friendship])
async def get_sent_pending_requests(
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Get a list of pending friend requests sent by the user."""
    logger.info(f"User {current_user.user_id} fetching their sent pending friend requests.")
    try:
        pending_requests = await crud.get_sent_pending_friend_requests(db, user_id=current_user.user_id)
        logger.info(f"Successfully fetched {len(pending_requests)} sent pending requests for user {current_user.user_id}.")
        return pending_requests
    except Exception as e:
        logger.exception(f"Error fetching sent pending requests for user {current_user.user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve sent pending requests.")


@router.put("/request/{requester_id}/accept", response_model=schemas.Friendship)
async def accept_friend_request(
    requester_id: int,
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Accept a friend request."""
    addressee_id = current_user.user_id
    logger.info(f"User {addressee_id} attempting to accept friend request from {requester_id}")

    friendship = await crud.get_friendship_by_users(db, user_id_1=requester_id, user_id_2=addressee_id)

    if not friendship or friendship.addressee_id != addressee_id or friendship.status != schemas.FriendshipStatus.pending:
        logger.warning(f"Friend request acceptance failed: No pending request found from {requester_id} for user {addressee_id}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending friend request from this user to you.")

    try:
        # Explicitly create the update object with ACCEPTED status
        friendship_update = schemas.FriendshipUpdate(status=schemas.FriendshipStatus.accepted)
        await crud.update_friendship(db, db_friendship=friendship, friendship_up=friendship_update)

        # --- Create Notification for the Requester ---
        await crud.create_notification(
            db=db,
            recipient_user_id=requester_id,
            notification_type=NotificationType.friend_request_accepted,
            message=f"{current_user.full_name or current_user.username} accepted your friend request.",
            related_user_id=addressee_id
        )
        # --- End Notification ---

        await db.commit()
        logger.info(f"User {addressee_id} successfully accepted friend request from {requester_id}.")
        
        updated_friendship = await crud.get_friendship_by_users(db=db, user_id_1=requester_id, user_id_2=addressee_id)
        return updated_friendship
    except Exception as e:
        logger.exception(f"Error accepting friend request from {requester_id} for user {addressee_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not accept friend request.")


@router.delete("/request/{requester_id}", status_code=status.HTTP_204_NO_CONTENT)
async def decline_friend_request(
    requester_id: int,
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Decline and delete a friend request."""
    addressee_id = current_user.user_id
    logger.info(f"User {addressee_id} attempting to decline friend request from {requester_id}")

    friendship = await crud.get_friendship_by_users(db, user_id_1=requester_id, user_id_2=addressee_id)

    if not friendship or friendship.addressee_id != addressee_id or friendship.status != schemas.FriendshipStatus.pending:
        logger.warning(f"Friend request decline failed: No pending request found from {requester_id} for user {addressee_id}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending friend request from this user to you.")

    try:
        await crud.delete_friendship(db, db_friendship=friendship)
        await db.commit()
        logger.info(f"User {addressee_id} successfully declined and deleted friend request from {requester_id}.")
        return
    except Exception as e:
        logger.exception(f"Error declining friend request from {requester_id} for user {addressee_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not decline friend request.") 