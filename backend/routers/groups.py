from fastapi import APIRouter, Depends, status, HTTPException, Path, Response, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import Annotated
from datetime import timedelta
from backend.dependencies import get_current_user
import logging

from jose import jwt, JWTError
import backend.models as models
from backend.models import GroupRole, AuditActionType

from backend.crud import (
    create_group, get_user_groups, get_group, is_member_of_group, add_user_to_group,
    get_user_role_in_group, get_user_by_user_id, get_group_members, 
    remove_user_from_group, get_group_member_with_user, get_group_audit_log_entries,
    get_users_by_ids, get_pending_invitations_for_group,
    update_group, calculate_group_net_balances, swap_owner_with_admin, update_member_role
) 
from backend.schemas import User, Group, GroupCreate, GroupUpdate, GroupMember, GroupMemberCreate, GroupActivityFeedResponse, AuditLogEntryResponse, GroupInvitation, UserRoleResponse, GroupMemberRoleUpdate
from backend.security import (
    create_access_token,
    oauth2_scheme, 
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
)
from backend.database import DbSessionDep
from backend.dependencies import get_current_user, validate_group_member
from backend.services.audit_service import record_group_activity
from fastapi_cache.decorator import cache

logger = logging.getLogger(__name__) # Get a logger for this module

router = APIRouter(
    prefix="/groups",
    tags=["groups"], 
)


@router.post("/", response_model=Group, status_code=status.HTTP_201_CREATED)
async def create_new_group(
    group_in: GroupCreate,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    logger.info(f"User {current_user.user_id} attempting to create group '{group_in.group_name}'")

    try:
        db_group = await create_group(group_in=group_in, db=db, creator_id=current_user.user_id)
        
        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=AuditActionType.group_created,
            group_id=db_group.group_id
        )

        await db.commit()
        await db.refresh(db_group)
        
        logger.info(f"User {current_user.user_id} successfully created group {db_group.group_id} ('{db_group.group_name}')")
        
        final_group = await get_group(group_id=db_group.group_id, db=db)
        return final_group

    except IntegrityError as e:
        logger.warning(f"IntegrityError by user {current_user.user_id} creating group '{group_in.group_name}': {e}") # Use warning for 4xx errors
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after login exception: {rollback_err}")
        
        detail = "Failed to create group. Potential conflict or invalid data."
        status_code = status.HTTP_400_BAD_REQUEST
        original_error_msg = str(e.orig).lower() if e.orig else ""
        if "foreign key constraint" in original_error_msg:
            detail = f"Creator user (ID: {current_user.user_id}) invalid."

        raise HTTPException(status_code=status_code, detail=detail) from e

    except Exception as e:
        logger.exception(f"Unexpected error by user {current_user.user_id} creating group '{group_in.group_name}'")
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after login exception: {rollback_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred",
        ) from e


@router.get("/{group_id}", response_model=Group)
async def read_group(
    group_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    logger.info(f"User {current_user.user_id} attempting to read group {group_id}")

    try:
        is_member = await is_member_of_group(db=db, user_id=current_user.user_id, group_id=group_id)
        if not is_member:
            logger.warning(f"User {current_user.user_id} forbidden access to group {group_id}.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not a member of the group")

        db_group = await get_group(db=db, group_id=group_id)
        if db_group is None:
            logger.warning(f"Group {group_id} not found for user {current_user.user_id}.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

        logger.info(f"User {current_user.user_id} successfully accessed group {group_id}")
        return db_group
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Error reading group {group_id} for user {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred",
        ) from e
    

@router.get("/", response_model=list[Group])
async def read_user_groups(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    try:
        logger.info(f"Fetching groups for user_id: {current_user.user_id}")
        groups = await get_user_groups(db=db, user_id=current_user.user_id)
        return groups
    
    except Exception as e:
        logger.exception(f"Error fetching groups for user_id: {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred",
        ) from e


@router.post(
    "/{group_id}/members",
    response_model=GroupMember, 
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "User not authorized to add members"},
        404: {"description": "Group or User to add not found"},
        409: {"description": "User already member of the group"},
    },
)
async def add_member_to_group(
    group_id: int,
    db: DbSessionDep,
    member_data: GroupMemberCreate,
    current_user: User = Depends(get_current_user),
    _=Depends(validate_group_member)
):
    requester_id = current_user.user_id
    user_id_to_add = member_data.user_id
    role_to_add = member_data.role

    logger.info(
        f"User {requester_id} attempting to add user {user_id_to_add} "
        f"with role {role_to_add.value} to group {group_id}"
    )

    try:
        # Get & check requester's role in this group
        requester_role = await get_user_role_in_group(
            db=db, user_id=requester_id, group_id=group_id
        )
        allowed_to_initiate_add = {GroupRole.owner, GroupRole.admin}
        if requester_role not in allowed_to_initiate_add:
            logger.warning(f"User {requester_id} (role: {requester_role}) forbidden to add members to group {group_id}.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to add members to this group")

        # Permission check
        if role_to_add == GroupRole.owner:
            logger.warning(f"User {requester_id} attempted to add user {user_id_to_add} as owner.")
            raise HTTPException(status_code=400, detail="Cannot add a member with the 'owner' role directly.")
        elif role_to_add == GroupRole.admin and requester_role != GroupRole.owner:
            logger.warning(f"Admin {requester_id} attempted to add user {user_id_to_add} as admin.")
            raise HTTPException(status_code=403, detail="Only group owners can add other admins.")

        # Check if user_id_to_add is already in the group
        user_to_add = await get_user_by_user_id(db=db, user_id=user_id_to_add)
        if not user_to_add:
            logger.warning(f"Add member failed: User {user_id_to_add} already in group {group_id}.")
            raise HTTPException(status_code=409, detail=f"User (ID: {user_id_to_add}) is already a member...")

        # Add member
        await add_user_to_group(
            db=db,
            group_id=group_id,
            user_id=user_id_to_add,
            role=role_to_add
        )
        logger.info(f"Successfully added user {user_id_to_add} to group {group_id} with role {role_to_add.value} by user {requester_id}")

        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=AuditActionType.member_added,
            group_id=group_id,
            target_user_membership_related=user_to_add
        )

        await db.commit()

        new_membership_details = await get_group_member_with_user(
            db=db,
            group_id=group_id,
            user_id=user_id_to_add
        )

        if not new_membership_details:
            logger.error(f"Could not retrieve newly added membership for user {user_id_to_add} in group {group_id}")
            raise HTTPException(status_code=500, detail="Failed to retrieve membership details after creation.")

        return new_membership_details
        
    except IntegrityError as e:
        logger.warning(f"IntegrityError adding user {current_user.user_id} to group {group_id}")
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after login exception: {rollback_err}")

        # --- MySQL Specific Error Handling ---
        detail = "An integrity error occurred." # Generic fallback
        status_code = status.HTTP_400_BAD_REQUEST # Default to 400 for integrity issues

        # Check the specific MySQL error code if available
        # Note: Accessing e.orig might depend on the DB driver (e.g., aiomysql, asyncmy)
        # Check your driver's documentation if e.orig or e.code doesn't work directly.
        # Let's assume e.orig provides access to the original DBAPI error.
        orig_error = getattr(e, 'orig', None)
        error_code = getattr(orig_error, 'errno', getattr(orig_error, 'args', [0])[0] if orig_error and hasattr(orig_error,'args') else 0) # Try common ways to get code

        if error_code == 1452: # MySQL code for Foreign Key Constraint Failure
            # Determine which FK failed if possible (more complex parsing needed)
            # Simplified: Assume it's either the group or the user to add
            detail = f"User to add (ID: {member_data.user_id}) not found, or the group does not exist."
            status_code = status.HTTP_400_BAD_REQUEST # 400 as input references non-existent entity
            # Or status_code = status.HTTP_404_NOT_FOUND if you prefer

        elif error_code == 1062: # MySQL code for Duplicate Entry (Unique Constraint)
            detail = f"User (ID: {member_data.user_id}) is already a member of this group."
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(status_code=status_code, detail=detail) from e
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception("An unexpected error occurred while adding user to group")
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after login exception: {rollback_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred",
        ) from e
    

# List Group Members
@router.get(
    "/{group_id}/members",
    response_model=list[GroupMember],
    responses={
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group not found"},
    },
)
async def read_group_members(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(..., ge=1),
):
    """Retrieves a list of members for a specific group."""
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve members for group {group_id}")

    try:
        # Check if group exists/user have access to this group
        group = await get_group(db=db, group_id=group_id)
        if not group:
            logger.warning(f"List members failed: Group {group_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

        is_member = await is_member_of_group(db=db, user_id=user_id, group_id=group_id)
        if not is_member:
            logger.warning(f"User {user_id} forbidden access to members of group {group_id}.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this group")

        # Get members
        members = await get_group_members(db=db, group_id=group_id)

        logger.info(f"User {user_id} successfully retrieved {len(members)} members for group {group_id}.")
        return members

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Error reading group members for group {group_id} by user {current_user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching group members."
        )


# Remove a Member
@router.delete(
    "/{group_id}/members/{user_id_to_remove}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "User not authorized to remove members"},
        404: {"description": "Group or Member not found"},
    }
)
async def remove_member_from_group_endpoint(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    user_id_to_remove: int = Path(..., ge=1, description="ID of the user to remove"),
    group_id: int = Path(..., ge=1),
):
    """
    Removes a specified user from a group based on role permissions.
    - Requires authenticated user to be Owner or Admin.
    - Owners can remove Admins/Members.
    - Admins can remove Members.
    - Cannot remove self.
    - Cannot remove the Owner.
    """
    requester_id = current_user.user_id
    logger.info(f"User {requester_id} attempting to remove user {user_id_to_remove} from group {group_id}")

    # Prevent removing self
    if requester_id == user_id_to_remove:
       raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself from the group. Please use the 'Leave Group' feature.")

    try:
        # Check group existence
        group = await get_group(db=db, group_id=group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # Balance Check: Ensure the user to be removed has a zero balance
        net_balances = await calculate_group_net_balances(db=db, group_id=group_id)
        user_balance = net_balances.get(user_id_to_remove)

        if user_balance is not None and user_balance != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove a member with an outstanding balance. Please settle all debts before removing the member."
            )

        # Get roles of both users (also confirms they are members)
        requester_role = await get_user_role_in_group(db=db, user_id=requester_id, group_id=group_id)
        target_member_role = await get_user_role_in_group(db=db, user_id=user_id_to_remove, group_id=group_id)

        if requester_role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this group.")

        if target_member_role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to remove is not a member of this group.")

        removed_user = await get_user_by_user_id(db=db, user_id=user_id_to_remove)

        if target_member_role == GroupRole.owner:
            logger.warning(f"User {requester_id} attempted to remove the owner (user {user_id_to_remove}).")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The group owner cannot be removed.")

        if requester_role == GroupRole.member:
            logger.warning(f"Member {requester_id} attempted to remove user {user_id_to_remove}.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Members cannot remove other members.")

        if requester_role == GroupRole.admin and target_member_role != GroupRole.member:
            logger.warning(f"Admin {requester_id} attempted to remove non-member role ({target_member_role.value}).")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins can only remove members.")

        removed = await remove_user_from_group(
            db=db, group_id=group_id, user_id_to_remove=user_id_to_remove
        )

        if not removed:
            logger.error(f"Removal reported failure for user {user_id_to_remove} despite checks.")
            raise HTTPException(status_code=500, detail="Failed to remove member.")
        
        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=AuditActionType.member_removed,
            group_id=group_id,
            target_user_membership_related=removed_user,
        )

        await db.commit()
        logger.info(f"User {requester_id} successfully removed user {user_id_to_remove} from group {group_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Unexpected error removing user {user_id_to_remove} from group {group_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while removing the member."
        )


@router.delete(
    "/{group_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave a group",
    responses={
        400: {"description": "Cannot leave with outstanding balance or if owner"},
        404: {"description": "Group not found or user is not a member"},
    }
)
async def leave_group(
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
    group_id: int = Path(..., ge=1),
):
    """
    Allows the current authenticated user to leave a group.
    - An owner cannot leave the group. They must transfer ownership first.
    - A member cannot leave if they have an outstanding balance.
    """
    user_id_to_leave = current_user.user_id
    logger.info(f"User {user_id_to_leave} attempting to leave group {group_id}")

    try:
        user_role = await get_user_role_in_group(db, user_id=user_id_to_leave, group_id=group_id)
        if user_role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not a member of this group.")

        if user_role == models.GroupRole.owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owners cannot leave the group. Please transfer ownership to another member first."
            )

        net_balances = await calculate_group_net_balances(db, group_id=group_id)
        user_balance = net_balances.get(user_id_to_leave, 0)
        if user_balance != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You cannot leave the group with an outstanding balance of {user_balance:,.0f} VND. Please settle all debts first."
            )

        was_removed = await remove_user_from_group(db, group_id=group_id, user_id_to_remove=user_id_to_leave)
        if not was_removed:
            # This case might be redundant if the role check passed, but good for safety
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to leave the group, you may have already left.")

        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=models.AuditActionType.member_left,
            group_id=group_id,
            target_user_membership_related=current_user
        )

        await db.commit()
        logger.info(f"User {user_id_to_leave} successfully left group {group_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.exception(f"Unexpected error for user {user_id_to_leave} leaving group {group_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to leave the group."
        )


@router.get(
    "/{group_id}/activities",
    response_model=GroupActivityFeedResponse,
    summary="Get Recent Activity for a Group (from Audit Log)",
    responses={
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group not found"},
    }
)
async def get_group_activity_feed_from_audit(
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
    group_id: int = Path(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    _=Depends(validate_group_member),
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} requesting activity feed for group {group_id} from audit log (skip: {skip}, limit: {limit})")

    try:
        # Fetch audit logs
        audit_entries = await get_group_audit_log_entries(
            db=db, group_id=group_id, skip=skip, limit=limit
        )

        if not audit_entries:
            return GroupActivityFeedResponse(group_id=group_id, activities=[])

        # Fetch all users in logs
        user_ids_to_fetch: set[int] = set()
        for entry in audit_entries:
            if entry.actor_user_id:
                user_ids_to_fetch.add(entry.actor_user_id)
            if entry.target_user_id:
                user_ids_to_fetch.add(entry.target_user_id)
            # If summary_message needs names from target_bill_id or target_payment_id's users,
            # you'd need to fetch those bills/payments and then their users.
            # For simplicity, we'll assume summary_message is self-contained or uses IDs for now.

        user_models_map: dict[int, models.User] = {}
        if user_ids_to_fetch:
            user_list = await get_users_by_ids(db=db, user_ids=list(user_ids_to_fetch))
            user_models_map = {user.user_id: user for user in user_list}

        # 3. Format into final response AuditLogEntryResponse
        response_activities: list[AuditLogEntryResponse] = []
        for entry_orm in audit_entries:
            actor_model = user_models_map.get(entry_orm.actor_user_id) if entry_orm.actor_user_id else None
            actor_schema = User.model_validate(actor_model) if actor_model else None
            
            # Use pre-generated summary_message or construct one
            display_msg = entry_orm.summary_message
            if not display_msg: # Fallback message construction if summary_message is None
                # This part requires fetching details of target_bill, target_payment, target_user names
                # to make a good message. This can get complex here if not pre-generated.
                # For now, let's assume summary_message is always populated by the action that created the log.
                actor_name_str = actor_model.username if actor_model and actor_model.username else "System"
                display_msg = f"{actor_name_str} performed action: {entry_orm.action_type.value}"
                if entry_orm.target_bill_id: display_msg += f" on bill {entry_orm.target_bill_id}"
                if entry_orm.target_payment_id: display_msg += f" on payment {entry_orm.target_payment_id}"
                if entry_orm.target_user_id: 
                    target_user_model = user_models_map.get(entry_orm.target_user_id)
                    target_user_name_str = target_user_model.username if target_user_model and target_user_model.username else f"user {entry_orm.target_user_id}"
                    display_msg += f" affecting {target_user_name_str}"


            response_activities.append(AuditLogEntryResponse(
                id=entry_orm.id,
                timestamp=entry_orm.timestamp,
                action_type=entry_orm.action_type,
                actor_user=actor_schema,
                display_message=display_msg,
                group_id=entry_orm.group_id, # Should always be the same as path group_id
                target_bill_id=entry_orm.target_bill_id,
                target_payment_id=entry_orm.target_payment_id,
                target_user_id=entry_orm.target_user_id
            ))
            
        return GroupActivityFeedResponse(group_id=group_id, activities=response_activities)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error fetching audit activity feed for group {group_id} by user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching group activity.",
        ) from e


@router.put("/{group_id}", response_model=Group)
async def edit_group_details(
    group_id: int,
    group_update_data: GroupUpdate,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    logger.info(f"User {current_user.user_id} attempting to update group {group_id} with data: {group_update_data.model_dump(exclude_unset=True)}")

    requester_role = await get_user_role_in_group(db=db, user_id=current_user.user_id, group_id=group_id)

    if requester_role not in {GroupRole.owner, GroupRole.admin}:
        logger.warning(f"User {current_user.user_id} (role: {requester_role}) forbidden to update group {group_id}.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this group. Must be an admin or owner."
        )
    
    if not group_update_data.model_dump(exclude_unset=True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided."
        )

    try:
        updated_db_group = await update_group(db=db, group_id=group_id, group_update=group_update_data)
        if updated_db_group is None:
            logger.warning(f"Update failed: Group {group_id} not found during update attempt by user {current_user.user_id}.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=AuditActionType.group_details_updated,
            group_id=group_id
        )
        
        await db.commit()
        await db.refresh(updated_db_group)
        
        logger.info(f"User {current_user.user_id} successfully updated group {group_id}.")
        return updated_db_group
    except IntegrityError as e: # Catch potential unique constraint violations if renaming, etc.
        logger.warning(f"IntegrityError by user {current_user.user_id} updating group {group_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update group. Potential conflict: {e.orig}"
        ) from e
    except Exception as e:
        logger.exception(f"Unexpected error by user {current_user.user_id} updating group {group_id}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the group.",
        ) from e


@router.get(
    "/{group_id}/invitations",
    response_model=list[GroupInvitation],
    summary="Get Pending Invitations for a Group",
    dependencies=[Depends(validate_group_member)],
    responses={
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group not found"},
    },
)
async def get_pending_group_invitations(
    group_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves a list of users who have been invited to the group but have not yet responded.
    Only accessible to members of the group.
    """
    logger.info(f"User {current_user.user_id} fetching pending invitations for group {group_id}")
    try:
        pending_invitations = await get_pending_invitations_for_group(db=db, group_id=group_id)
        logger.info(f"User {current_user.user_id} successfully fetched {len(pending_invitations)} pending invitations for group {group_id}")
        return pending_invitations
    
    except Exception as e:
        logger.exception(f"Error fetching pending invitations for group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve pending invitations."
        )


@router.get("/{group_id}/user-role", response_model=UserRoleResponse)
async def get_user_role_endpoint(
    group_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    """
    Returns the role of the current user in a specific group.
    """
    logger.info(f"User {current_user.user_id} checking their role for group {group_id}")

    try:
        user_role = await get_user_role_in_group(db=db, user_id=current_user.user_id, group_id=group_id)

        if user_role is None:
            logger.warning(f"User {current_user.user_id} is not a member of group {group_id}, role check failed.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in this group."
            )
        
        logger.info(f"Role for user {current_user.user_id} in group {group_id} is {user_role.value}")
        return UserRoleResponse(role=user_role)

    except HTTPException:
        raise # Re-raise HTTPException directly to preserve its status code and detail

    except Exception as e:
        logger.exception(f"Unexpected error checking role for user {current_user.user_id} in group {group_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while checking user role."
        ) from e


@router.get("/{group_id}/members/{user_id}/role", response_model=UserRoleResponse)
async def get_user_role_in_group_endpoint(
    group_id: int,
    user_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user), # Ensures caller is authenticated
):
    """Get a user's role in a specific group."""
    # Ensure the user whose role is being requested is in the group
    role = await get_user_role_in_group(db, user_id=user_id, group_id=group_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not a member of this group.")
    
    # Ensure the current_user (the one making the request) is a member of the group
    is_requester_member = await is_member_of_group(db, user_id=current_user.user_id, group_id=group_id)
    if not is_requester_member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to view information about this group.")

    return UserRoleResponse(role=role)


@router.put("/{group_id}/members/{user_id}/role", response_model=GroupMember)
async def update_member_role_endpoint(
    group_id: int,
    user_id: int,
    role_update: GroupMemberRoleUpdate,
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
):
    """
    Promote or demote a user within a group.
    - Owners can promote/demote Admins and Members.
    - Admins can promote/demote Members.
    - Promoting an Admin to Owner swaps roles with the current Owner.
    """
    requester_id = current_user.user_id
    new_role = role_update.role

    # --- Authorization ---
    requester_membership = await get_group_member_with_user(db, group_id=group_id, user_id=requester_id)
    target_membership = await get_group_member_with_user(db, group_id=group_id, user_id=user_id)

    if not requester_membership or not target_membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this group.")

    requester_role = requester_membership.role
    target_role = target_membership.role
    
    # Define role hierarchy
    role_hierarchy = {models.GroupRole.owner: 2, models.GroupRole.admin: 1, models.GroupRole.member: 0}

    # Rule: Cannot change your own role
    if requester_id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own role.")

    # Rule: Requester must have a higher role than the target to modify them
    if role_hierarchy[requester_role] <= role_hierarchy[target_role]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage members with a role lower than your own.")

    # Rule: The new role must be different and cannot be higher than the requester's role (except for owner swap)
    if new_role == target_role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User is already a {new_role.value}.")

    # --- Special Case: Owner promotes an Admin ---
    if requester_role == models.GroupRole.owner and target_role == models.GroupRole.admin and new_role == models.GroupRole.owner:
        try:
            # We need the full membership object back with the user loaded for the response
            updated_membership = await swap_owner_with_admin(db, group_id=group_id, current_owner_id=requester_id, new_owner_id=user_id)
            if not updated_membership:
                raise # Should be caught by the general exception handler

            # Log the promotion of the new owner
            await record_group_activity(
                db=db,
                actor_user=current_user,
                action_type=models.AuditActionType.member_role_promoted,
                group_id=group_id,
                target_user_membership_related=target_membership.user,
                target_role=new_role
            )
            # Log the demotion of the old owner
            await record_group_activity(
                db=db,
                actor_user=current_user, # The original requester is still the actor
                action_type=models.AuditActionType.member_role_demoted,
                group_id=group_id,
                target_user_membership_related=current_user,
                target_role=models.GroupRole.admin
            )

            await db.commit()
            return updated_membership
        except Exception as e:
            await db.rollback()
            logger.exception(f"Error during owner swap between {requester_id} and {user_id} in group {group_id}: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred during the owner swap.")

    # --- Standard Promotion/Demotion ---
    if role_hierarchy[new_role] >= role_hierarchy[requester_role]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot promote a member to your own role or higher.")

    try:
        updated_membership = await update_member_role(db, group_id=group_id, user_id=user_id, new_role=new_role)
        if not updated_membership:
            raise # Should be caught by the general exception handler

        action_type = models.AuditActionType.member_role_promoted if role_hierarchy[new_role] > role_hierarchy[target_role] else models.AuditActionType.member_role_demoted

        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=action_type,
            group_id=group_id,
            target_user_membership_related=target_membership.user,
            target_role=new_role
        )
        await db.commit()
        
        # We need to eager load the user for the response model
        final_membership = await get_group_member_with_user(db, group_id=group_id, user_id=user_id)
        return final_membership

    except Exception as e:
        await db.rollback()
        logger.exception(f"Error updating role for user {user_id} in group {group_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not update member role.")