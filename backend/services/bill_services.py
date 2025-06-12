from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


from backend.database import DbSessionDep
from backend.crud import (
    validate_member_ids_in_group, create_bill,
    update_bill, delete_bill
)
import backend.schemas as schemas
from backend.schemas import BillCreate, BillUpdate
import backend.models as models
from backend.models import SplitMethod, AuditActionType
from backend.services.audit_service import record_group_activity
import logging

logger = logging.getLogger(__name__)

async def validate_bill_modification(
    db: AsyncSession,
    bill_in: BillCreate | BillUpdate,
    group_id: int
):
    user_ids_to_validate: set[int] = set()

    # Add initial payers
    for payment in bill_in.initial_payments:
        user_ids_to_validate.add(payment.user_id)

    # Add users from bill parts (if applicable)
    if bill_in.split_method == SplitMethod.percentage and bill_in.bill_parts:
        for part in bill_in.bill_parts:
            user_ids_to_validate.add(part.user_id)

    # Add users from item splits (if applicable)
    elif bill_in.split_method == SplitMethod.item and bill_in.items:
        for item in bill_in.items:
            if item.splits: # Validator ensures splits exist if method is item
                for split in item.splits:
                    user_ids_to_validate.add(split.user_id)

    # Validate all collected user IDs against group membership
    if user_ids_to_validate: # Only run DB check if there are IDs to validate
        # Convert set to list for the CRUD function
        invalid_ids_list = list(user_ids_to_validate)
        are_users_valid_members = await validate_member_ids_in_group(
            db=db, user_ids=invalid_ids_list, group_id=group_id
        )
        if not are_users_valid_members:
            # Log which IDs were attempted
            logger.warning(f"Provided user IDs {invalid_ids_list} contains non-members of group {group_id}.")
            # Return 400 Bad Request because input data references invalid users for this group
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more users involved in payments or splits are not valid members of this group."
            )
        

async def update_bill_service(
    db: AsyncSession,
    bill_to_update: models.Bill,
    bill_in: schemas.BillUpdate,
    updater_user: models.User,
    group_id: int
) -> models.Bill:
    """
    Service to update a bill, including payload validation and audit logging.
    Manages the transaction. Can raise HTTPException.
    """
    bill_id_for_log = bill_to_update.bill_id 

    try:
        await validate_bill_modification(db=db, bill_in=bill_in, group_id=group_id)
        
        updated_bill = await update_bill(
            db=db, 
            db_bill=bill_to_update, 
            bill_in=bill_in,
        )

        await record_group_activity(
            db=db,
            actor_user=updater_user,
            action_type=AuditActionType.bill_updated,
            group_id=group_id,
            target_bill=updated_bill
        )

        await db.commit()
        await db.refresh(updated_bill)
        
        return updated_bill

    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"IntegrityError updating bill {bill_id_for_log} by {updater_user.user_id}: {e.orig}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Data conflict during bill update: {e.orig}") from e
    
    except HTTPException:
        raise
    
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error in update_bill_service for bill {bill_id_for_log} by {updater_user.user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update bill.") from e
    

async def delete_bill_service(
    db: AsyncSession,
    bill_id: models.Bill,
    deleter_user: models.User,
    group_id: int
) -> bool:
    """
    Service to update a bill, including payload validation and audit logging.
    Manages the transaction. Can raise HTTPException.
    """
    try:
        deleted = await delete_bill(db=db, bill_id=bill_id)

        if not deleted:
            logger.warning(
                f"Bill {bill_id} not found during delete operation for user {deleter_user.user_id}, "
                "possibly already deleted by another request."
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found or failed to delete.")


        await record_group_activity(
            db=db,
            actor_user=deleter_user,
            action_type=AuditActionType.bill_deleted,
            group_id=group_id,
        )

        await db.commit()
        return True

    except IntegrityError as e:
        await db.rollback()
        logger.warning(f"IntegrityError deleting bill {bill_id} by {deleter_user.user_id}: {e.orig}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Data conflict during bill deletion: {e.orig}") from e
    
    except HTTPException:
        raise
    
    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error in delete_bill_service for bill {bill_id} by {deleter_user.user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete bill.") from e