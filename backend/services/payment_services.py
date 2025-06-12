from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.database import DbSessionDep
from backend.crud import (
    validate_member_ids_in_group, get_group, get_bill,
    create_payment, get_user_by_user_id
)
import backend.schemas as schemas
from backend.schemas import BillCreate, BillUpdate
import backend.models as models
from backend.models import SplitMethod, AuditActionType
from backend.services.audit_service import record_group_activity
import logging

logger = logging.getLogger(__name__)

async def validate_payer_payee(
    db: AsyncSession,
    payer_id: int,
    payee_id: int,
    group_id: int,
):
    if payer_id == payee_id:
        logger.warning(
            f"Validation failed for payment in group {group_id}: Payer {payer_id} cannot be the same as payee."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payer and payee cannot be the same user."
        )

    # Check if both payer and payee are members of the group
    user_ids_to_check = [payer_id, payee_id]
    are_all_users_group_members = await validate_member_ids_in_group(
        db=db, user_ids=user_ids_to_check, group_id=group_id
    )

    if not are_all_users_group_members:
        db_group = await get_group(db=db, group_id=group_id)

        # Group doesn't exist
        if not db_group:
            logger.warning(
                f"Validation failed for payment: Group {group_id} not found (payer: {payer_id}, payee: {payee_id})."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found."
            )
        
        # Payer or payee not in group
        else:
            logger.warning(
                f"Validation failed for payment in group {group_id}: Payer {payer_id} or payee {payee_id} is not a member."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payer or payee is not a valid member of this group."
            )
        

# async def create_payment_service(
#     db: AsyncSession,
#     payment_in: schemas.PaymentCreate,
#     payer: models.User,
#     group_id: int
# ) -> models.Payment:
#     """
#     Service to create a payment, including validation and audit logging.
#     Manages the transaction. Can raise HTTPException.
#     """
#     payer_id = payer.user_id
#     payee_id = payment_in.payee_id

#     payee = await get_user_by_user_id(db=db, user_id=payee_id)

#     try:
#         validate_payer_payee(
#             db=db,
#             payer_id=payer_id,
#             payee_id=payee_id,
#             group_id=group_id
#         )

#         if payment_in.bill_id is not None:
#             bill = await get_bill(db=db, bill_id=payment_in.bill_id)
#             if bill is None or bill.group_id != group_id:
#                 logger.warning(
#                     f"Payment creation failed: Bill {payment_in.bill_id}"
#                     f"not found or not in group {group_id}."
#                 )
#                 raise HTTPException(
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     detail=f"Bill specified (ID: {payment_in.bill_id}) is invalid"
#                            f"or does not belong to this group."
#                 )
            
#         db_payment = await create_payment(
#             payment_in=payment_in,
#             db=db,
#             creator_id=payer_id,
#             group_id=group_id
#         )

#         await record_group_activity(
#             db=db,
#             actor_user=payer,
#             action_type=AuditActionType.payment_created,
#             group_id=group_id,
#             target_payment=db_payment,
#             target_user_membership_related=payee
#         )

#         await db.commit()
#         await db.refresh(db_payment)
#         return db_payment

#     except IntegrityError as e:
#         await db.rollback()
#         logger.warning(
#             f"IntegrityError creating payment in group {group_id} by {payer.user_id} for payee {payment_in.payee_id}: {e.orig}"
#         )
#         raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Data conflict: {e.orig}") from e

#     except HTTPException:
#         raise

#     except Exception as e:
#         await db.rollback()
#         logger.exception(
#             f"Unexpected error in create_payment_service for group {group_id} by {payer.user_id} for payee {payment_in.payee_id}: {e}"
#         )
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create payment due to a server error.") from e