from fastapi import APIRouter, Depends, status, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
from enum import Enum
from typing import Optional
from fastapi_cache.decorator import cache

from backend.crud import (
    get_group, is_member_of_group,
    create_bill, validate_member_ids_in_group,
    get_bill, get_group_bills,
    create_payment, get_payment, get_group_payments,
    delete_payment, update_payment
)
from backend.schemas import (
    Payment, PaymentCreate, User, PaymentUpdate
)
import backend.models as models
from backend.models import AuditActionType
from backend.database import DbSessionDep
from backend.dependencies import (
    get_current_user, validate_group_member,
    get_validated_payment_for_group, authorize_payment_operation,
    get_user_by_user_id
)
from backend.services.audit_service import record_group_activity
from backend.services.payment_services import validate_payer_payee


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/groups/{group_id}/payments",
    tags=["payments"],
)

class PaymentSortBy(str, Enum):
    created_at = "created_at"
    amount = "amount"

class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"

class PaymentFilterType(str, Enum):
    all = "all"
    involving = "involving"
    from_member = "from_member"
    to_member = "to_member"
    between = "between"

@router.post(
    "/",
    response_model=Payment,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid input data (e.g., payee not in group, payer=payee, invalid bill)"},
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group or specified Bill not found"},
        422: {"description": "Validation Error (schema level)"},
        500: {"description": "Internal server error"},
    }
)
async def create_new_payment(
    payment_in: PaymentCreate,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(...),
):
    payer_id = current_user.user_id
    payee_id = payment_in.payee_id

    logger.info(
        f"User {payer_id} attempting to record payment of {payment_in.amount}"
        f"to user {payee_id} in group {group_id}"
    )

    try:
        # Validate both in group and are different users
        await validate_payer_payee(
            db=db,
            payer_id=payer_id,
            payee_id=payee_id,
            group_id=group_id,
        )
        
        payee = await get_user_by_user_id(db=db, user_id=payee_id)
        if not payee:
            logger.warning(f"Payment creation failed: Payee user {payee_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payee user (ID: {payee_id}) not found.")

        
        # Check bill
        if payment_in.bill_id is not None:
            bill = await get_bill(db=db, bill_id=payment_in.bill_id)
            if bill is None or bill.group_id != group_id:
                logger.warning(
                    f"Payment creation failed: Bill {payment_in.bill_id}"
                    f"not found or not in group {group_id}."
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Bill specified (ID: {payment_in.bill_id}) is invalid"
                           f"or does not belong to this group."
                )

        # Create payment and log
        db_payment = await create_payment(
            payment_in=payment_in,
            db=db,
            creator_id=current_user.user_id,
            group_id=group_id
        )

        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=AuditActionType.payment_created,
            group_id=group_id,
            target_payment=db_payment,
            target_user_membership_related=payee
        )

        db.commit()

        final_payment = await get_payment(
            db=db,
            payment_id=db_payment.payment_id,
            group_id=group_id,
        )
        logger.info(
            f"User {payer_id} successfully recorded payment {db_payment.payment_id}"
            f"of {db_payment.amount} to user {payee_id} in group {group_id}"
        )
        return final_payment
    
    except IntegrityError as e:
        logger.warning(
            f"IntegrityError during payment creation for group {group_id} by user {payer_id}: {e}"
        )
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after payment creation IntegrityError: {rollback_err}")

        detail = "Failed to record payment due to data conflict or invalid reference."
        status_code = status.HTTP_400_BAD_REQUEST

        original_error_msg = str(e.orig).lower() if e.orig else ""
        if "foreign key constraint" in original_error_msg:
            detail = "Invalid reference provided (group, payer, payee, or bill)."

        raise HTTPException(status_code=status_code, detail=detail) from e

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Unexpected error during payment creation for group {group_id} by user {payer_id}"
        )
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after unexpected payment creation error: {rollback_err}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while recording the payment.",
        ) from e


@router.get(
    "/{payment_id}",
    response_model=Payment,
        responses={
        404: {"description": "Payment not found or user not involved"},
        500: {"description": "Internal server error"}
    }
)
async def read_payment(
    payment_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(...),
    _=Depends(validate_group_member),
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve payment {payment_id} in group {group_id}.")

    try:
        db_payment = await get_payment(
            db=db,
            payment_id=payment_id,
            group_id=group_id,
        )

        if db_payment is None:
            logger.warning(f"Payment {payment_id} not found in group {group_id} or user {user_id} not involved.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )

        logger.info(f"User {user_id} successfully retrieved payment {payment_id} from group {group_id}.")
        return db_payment
    
    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error retrieving payment {payment_id} in group {group_id} for user {user_id}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred",
        ) from e


@router.get(
    "/",
    response_model=list[Payment],
)
@cache(expire=300)
async def read_group_payments(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of records to return"),
    group_id: int = Path(..., description="ID of the group to retrieve payments for", ge=1),
    sort_by: PaymentSortBy = Query(PaymentSortBy.created_at, description="Field to sort payments by."),
    sort_order: SortOrder = Query(SortOrder.desc, description="Order to sort payments in."),
    filter_type: PaymentFilterType = Query(PaymentFilterType.all, description="Type of filter to apply."),
    member_a_id: Optional[int] = Query(None, description="Primary member for filtering."),
    member_b_id: Optional[int] = Query(None, description="Secondary member for 'between' filter."),
    _=Depends(validate_group_member)
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve payments for group {group_id} (skip={skip}, limit={limit}).")

    try:
        payments = await get_group_payments(
            db=db,
            group_id=group_id,
            skip=skip,
            limit=limit,
            sort_by=sort_by.value,
            sort_order=sort_order.value,
            filter_type=filter_type.value,
            member_a_id=member_a_id,
            member_b_id=member_b_id,
        )

        logger.info(f"User {user_id} successfully retrieved {len(payments)} payments for group {group_id}.")
        return payments

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error retrieving payments for group {group_id} by user {user_id}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving payments.",
        ) from e
    

@router.delete(
    "/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Payment",
    responses={
        403: {"description": "User not authorized to delete this payment"},
        404: {"description": "Group or Payment not found"},
    }
)
async def delete_payment_endpoint(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(..., ge=1, description="ID of the group the payment belongs to"),
    payment_id: int = Path(..., ge=1, description="ID of the payment to delete"),
    _=Depends(get_validated_payment_for_group),
    __=Depends(authorize_payment_operation)
):
    requester_user_id = current_user.user_id
    logger.info(f"User {requester_user_id} attempting to delete payment {payment_id}.")

    # If code execution reaches here, the user is authorized.

    try:
        # Delete payment
        deleted = await delete_payment(db=db, payment_id=payment_id) # Use your actual crud path

        if not deleted:
            logger.warning(
                f"Payment {payment_id} not found during delete operation by user {requester_user_id}, "
                "possibly already deleted."
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found or failed to delete.")

        logger.info(f"User {requester_user_id} successfully deleted payment {payment_id}.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise

    except SQLAlchemyError as e:
        logger.exception(f"Database error deleting payment {payment_id} by user {requester_user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during payment deletion.") from e
    
    except Exception as e:
        logger.exception(
            f"Unexpected error during deletion of payment {payment_id} by user {requester_user_id}: {e}"
        )
        try: await db.rollback() # Safeguard rollback
        except Exception as rb_ex: logger.error(f"Rollback failed after error: {rb_ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        ) from e
    

@router.put(
    "/{payment_id}",
    response_model=Payment,
    status_code=status.HTTP_200_OK,
    summary="Update a Payment",
    responses={
        403: {"description": "User not authorized to update this payment"},
        404: {"description": "Group or Payment not found"},
        422: {"description": "Validation Error in request body"},
    }
)
async def update_payment_endpoint(
    payment_update_data: PaymentUpdate,
    db: DbSessionDep,
    group_id: int = Path(..., ge=1, description="ID of the group the bill belongs to"),
    payment_id: int = Path(..., ge=1, description="ID of the payment to update"),
    current_user: User = Depends(get_current_user),
    db_payment: models.Payment = Depends(get_validated_payment_for_group),
    _: None = Depends(authorize_payment_operation), # Authorization check
):
    requester_user_id = current_user.user_id
    logger.info(f"User {requester_user_id} attempting to update payment {db_payment.payment_id} "
                f"in group {db_payment.group_id}.")

    try:
        updated_payment = await update_payment(
            db=db,
            db_payment=db_payment,
            payment_in=payment_update_data
        )

        payment = await get_payment(
            db=db,
            payment_id=updated_payment.payment_id,
            group_id=group_id,
        )

        if not payment:
            logger.error(
                f"CRITICAL: Payment {updated_payment.payment_id} updated by user {requester_user_id} " # Adjust .id
                f"but could not be re-fetched for response."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment updated but failed to retrieve for response."
            )

        logger.info(f"User {requester_user_id} successfully updated payment {payment.payment_id}.") # Adjust .id
        return payment

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Unexpected error during update of payment {payment_id} in group {group_id} by user {requester_user_id}: {e}"
        )
        
        try:
            await db.rollback()
        except Exception as rb_ex:
            logger.error(f"Rollback failed after an error during payment update: {rb_ex}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to update the payment."
        )