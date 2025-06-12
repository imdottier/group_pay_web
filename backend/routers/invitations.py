from fastapi import APIRouter, Depends, status, HTTPException, Path
from sqlalchemy.exc import IntegrityError
import logging
from datetime import datetime, timezone

from backend import crud, schemas
from backend.database import DbSessionDep
from backend.dependencies import get_current_user
from backend.models import GroupRole, AuditActionType, GroupInvitationStatus, NotificationType
from backend.services.audit_service import record_group_activity

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/invitations",
    tags=["group-invitations"],
    responses={401: {"description": "Not authenticated"}},
)

@router.post("/groups/{group_id}", response_model=schemas.GroupInvitation, status_code=status.HTTP_201_CREATED)
async def send_group_invitation(
    group_id: int,
    invitation: schemas.GroupInvitationCreate,
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Send an invitation for a user to join a group."""
    inviter_id = current_user.user_id
    invitee_id = invitation.invitee_id
    logger.info(f"User {inviter_id} attempting to invite user {invitee_id} to group {group_id}")

    # Authorization: Check if inviter is an owner or admin of the group
    inviter_role = await crud.get_user_role_in_group(db, user_id=inviter_id, group_id=group_id)
    if not inviter_role or inviter_role not in [GroupRole.owner, GroupRole.admin]:
        logger.warning(f"Authorization failed: User {inviter_id} with role {inviter_role} tried to invite to group {group_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to invite users to this group.")

    # Check if invitee exists
    invitee = await crud.get_user_by_user_id(db, user_id=invitation.invitee_id)
    if not invitee:
        logger.warning(f"Invitation failed: Invitee user {invitee_id} not found (sent by {inviter_id}).")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to invite not found.")

    # Check if user is already a member
    if await crud.is_member_of_group(db, user_id=invitee_id, group_id=group_id):
        logger.warning(f"Invitation failed: User {invitee_id} is already a member of group {group_id} (sent by {inviter_id}).")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member of this group.")

    try:
        # Check for an existing invitation
        existing_invitation = await crud.get_invitation_by_group_and_invitee(db, group_id=group_id, invitee_id=invitee_id)

        if existing_invitation:
            if existing_invitation.status == GroupInvitationStatus.pending:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pending invitation already exists for this user and group.")
            
            # If invitation was declined or accepted (and user left), "resend" it by updating it
            existing_invitation.status = GroupInvitationStatus.pending
            existing_invitation.created_at = datetime.now(timezone.utc)
            existing_invitation.inviter_id = inviter_id
            db.add(existing_invitation)
            invitation_to_return = existing_invitation
            logger.info(f"Re-sending invitation to user {invitee_id} for group {group_id}.")
        else:
            # Create a new invitation if none exists
            invitation_to_return = await crud.create_group_invitation(db, inv_in=invitation, group_id=group_id, inviter_id=inviter_id)
            logger.info(f"Sending new invitation to user {invitee_id} for group {group_id}.")

        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=AuditActionType.member_invited,
            group_id=group_id,
            target_user_membership_related=invitee
        )
        
        # --- Create Notification for the Invitee ---
        group = await crud.get_group(db, group_id=group_id) # Fetch group for name
        if group:
            await crud.create_notification(
                db=db,
                recipient_user_id=invitee_id,
                notification_type=NotificationType.GROUP_INVITE,
                message=f"{current_user.full_name or current_user.username} invited you to join the group '{group.group_name}'.",
                related_group_id=group_id,
                related_user_id=inviter_id
            )
        # --- End Notification ---

        await db.commit()
        
        # After commit, re-fetch the invitation using the function that loads all relationships
        final_invitation = await crud.get_group_invitation_by_id(db, invitation_id=invitation_to_return.invitation_id)

        if not final_invitation:
            logger.error(f"Could not retrieve new invitation for user {invitee_id} in group {group_id} after creation.")
            raise HTTPException(status_code=500, detail="Failed to retrieve invitation details after creation.")

        logger.info(f"User {inviter_id} successfully invited user {invitee_id} to group {group_id}. Invitation ID: {final_invitation.invitation_id}")
        return final_invitation
        
    except IntegrityError as e: # Keep as a fallback, though less likely to be hit
        logger.warning(f"Invitation failed: IntegrityError (likely duplicate) when inviting {invitee_id} to group {group_id} by {inviter_id}.")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An unexpected database error occurred.")
    except HTTPException:
        # Re-raise HTTPExceptions to avoid them being caught by the generic Exception handler
        raise
    except Exception as e:
        logger.exception(f"Error sending group invitation from {inviter_id} to {invitee_id} for group {group_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not send group invitation.")


@router.get("/pending", response_model=list[schemas.GroupInvitationInfo])
async def get_my_pending_invitations(
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Get the current user's pending group invitations."""
    logger.info(f"User {current_user.user_id} fetching their pending group invitations.")
    try:
        invitations = await crud.get_pending_invitations_for_user(db, user_id=current_user.user_id)
        return invitations
    except Exception as e:
        logger.exception(f"Error fetching pending invitations for user {current_user.user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch pending invitations.")


@router.put("/{invitation_id}", response_model=schemas.GroupInvitation)
async def respond_to_group_invitation(
    invitation_id: int,
    response: schemas.GroupInvitationUpdate,
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """Accept or decline a group invitation."""
    logger.info(f"User {current_user.user_id} attempting to respond to invitation {invitation_id} with status '{response.status.value}'.")
    invitation = await crud.get_group_invitation_by_id(db, invitation_id=invitation_id)

    if not invitation or invitation.invitee_id != current_user.user_id:
        logger.warning(f"Invitation response failed: User {current_user.user_id} tried to access invalid/unauthorized invitation {invitation_id}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found or you are not the invitee.")

    if invitation.status != schemas.GroupInvitationStatus.pending:
        logger.warning(f"Invitation response failed: User {current_user.user_id} tried to respond to already actioned invitation {invitation_id} (status: {invitation.status.value}).")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This invitation has already been responded to.")

    if response.status not in [schemas.GroupInvitationStatus.accepted, schemas.GroupInvitationStatus.declined]:
        logger.warning(f"Invitation response failed: User {current_user.user_id} provided invalid status '{response.status.value}' for invitation {invitation_id}.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status. Must be 'accepted' or 'declined'.")

    try:
        await crud.update_group_invitation(db, db_invitation=invitation, inv_up=response)
        await db.commit()
        
        # Re-fetch the invitation to get the fully loaded object for the response
        final_invitation = await crud.get_group_invitation_by_id(db, invitation_id=invitation_id)

        logger.info(f"User {current_user.user_id} successfully responded to invitation {invitation_id} with status '{response.status.value}'.")
        return final_invitation
    except Exception as e:
        logger.exception(f"Error responding to group invitation {invitation_id} for user {current_user.user_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not respond to invitation.") 