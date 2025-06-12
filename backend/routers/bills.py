from fastapi import APIRouter, Depends, status, HTTPException, Path, Response, Query, UploadFile, File, Form
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
from fastapi_cache.decorator import cache
import json
from typing import Optional

from backend.crud import (
    get_group, is_member_of_group,
    create_bill, validate_member_ids_in_group,
    get_bill, get_group_bills,
    get_user_role_in_group, delete_bill,
    update_bill
)
from backend.schemas import (
    BillCreate, Bill, User, SplitMethod, GroupRole, BillUpdate
)
import backend.models as models
from backend.database import DbSessionDep
from backend.dependencies import (
    get_current_user, validate_group_member,
    get_validated_bill_for_group, authorize_bill_operation
)
from backend.services.bill_services import (
    validate_bill_modification,
    update_bill_service, delete_bill_service
)
from backend.services.audit_service import record_group_activity
from backend.services.gcs_service import upload_receipt_to_gcs
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/groups/{group_id}/bills",
    tags=["bills"],
)


@router.post(
    "/",
    response_model=Bill, # Only import Bill here
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid input data (e.g., payer not in group)"},
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group not found"},
        422: {"description": "Validation Error (e.g., percentages don't sum)"},
        500: {"description": "Internal server error"},
    }
)
async def create_new_bill(
    db: DbSessionDep,
    group_id: int = Path(...),
    bill_data: str = Form(...),
    receipt_image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    _=Depends(validate_group_member),
):
    logger.info(f"User {current_user.user_id} attempting to create a bill in group {group_id}")

    try:
        # Pydantic v2 allows parsing from a JSON string
        bill_in = BillCreate.parse_raw(bill_data)
    except Exception as e:
        logger.warning(f"Failed to parse bill_data JSON for user {current_user.user_id}: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid bill data format: {e}")

    image_url = None
    if receipt_image:
        try:
            image_url = await upload_receipt_to_gcs(
                file=receipt_image,
                group_id=group_id,
                bill_title=bill_in.title
            )
            # Add the URL to the bill creation data
            bill_in.receipt_image_url = image_url
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to upload receipt image for group {group_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload receipt image.")

    logger.info(
        f"User {current_user.user_id} attempting to create bill '{bill_in.title}' in group {group_id}"
    )

    try:
        await validate_bill_modification(db=db, bill_in=bill_in, group_id=group_id)
        
        db_bill = await create_bill(
            db=db, 
            bill_in=bill_in, 
            creator_id=current_user.user_id, 
            group_id=group_id
        )

        await record_group_activity(
            db=db,
            actor_user=current_user,
            action_type=models.AuditActionType.bill_created,
            group_id=group_id,
            target_bill=db_bill
        )

        await db.commit()
        await db.refresh(db_bill)
        
        final_bill = await get_bill(db=db, bill_id=db_bill.bill_id)
        logger.info(
            f'''User {current_user.user_id} successfully created bill
            {final_bill.bill_id} ('{final_bill.title}') in group {group_id}''')
        return final_bill
    
    except IntegrityError as e:
        logger.warning(
            f'''IntegrityError during bill creation for group {group_id}
            by user {current_user.user_id}: {e}''')
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after bill creation IntegrityError: {rollback_err}")

        detail = "Failed to create bill due to data conflict or invalid reference."
        status_code = status.HTTP_400_BAD_REQUEST

        original_error_msg = str(e.orig).lower() if e.orig else ""
        if "foreign key constraint" in original_error_msg:
            detail = "Invalid user reference provided (creator or initial payer)."

        raise HTTPException(status_code=status_code, detail=detail) from e
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(
            f'''Unexpected error during bill creation for
            group {group_id} by user {current_user.user_id}''')
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after unexpected bill creation error: {rollback_err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the bill.", # Generic detail
        ) from e
    

@router.get(
    "/{bill_id}",
    response_model=Bill,
    responses={
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group or Bill not found / Bill not in group"},
        500: {"description": "Internal server error"},
    },
)
async def read_bill(
    bill_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(...),
    _=Depends(validate_group_member),
):
    logger.info(f"User {current_user.user_id} attempting to read bill {bill_id} in group {group_id}")

    try:        
        db_bill = await get_bill(db=db, bill_id=bill_id)
        if db_bill is None or db_bill.group_id != group_id:
            logger.warning(
                f'''Read bill failed: Bill {bill_id} not found or
                does not belong to group {group_id}.'''
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found in this group"
            )
        return db_bill
    
    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f'''Unexpected error reading bill {bill_id}
            in group {group_id} for user {current_user.user_id}''')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred",
        ) from e
    

@router.get(
    "/",
    response_model=list[Bill],
    responses={
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group not found"},
        500: {"description": "Internal server error"},
    }
)
# @cache(expire=300) // Temporarily disabled for debugging stale data issue
async def read_group_bills(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(...),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    _=Depends(validate_group_member),
):
    logger.info(f"User {current_user.user_id} attempting to read bills for group {group_id}")

    try:
        db_group_bills = await get_group_bills(
            db=db,
            group_id=group_id,
            skip=skip,
            limit=limit
        )
        logger.info(
            f"User {current_user.user_id} successfully fetched {len(db_group_bills)} bills for group {group_id}"
        )
        return db_group_bills  # Return the bills

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Unexpected error reading bills for group {group_id} by user {current_user.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching bills.",
        ) from e


@router.delete(
    "/{bill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Bill successfully deleted"},
        403: {"description": "Not authorized to delete this bill"},
        404: {"description": "Bill not found"},
    },
)
async def delete_bill(
    bill_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    _=Depends(validate_group_member),
):
    """
    Delete a bill. Only the bill creator, group admin, or group owner can delete a bill.
    """
    try:
        # Get the bill with its group relationship
        db_bill = await get_bill(db=db, bill_id=bill_id)
        if not db_bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bill not found",
            )

        # Get user's role in the group
        user_role = await get_user_role_in_group(
            db=db,
            user_id=current_user.user_id,
            group_id=db_bill.group_id
        )

        # Check if user is authorized to delete
        if (db_bill.created_by != current_user.user_id and 
            user_role not in [GroupRole.admin, GroupRole.owner]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the bill creator, group admin, or group owner can delete this bill",
            )

        # Delete the bill
        await delete_bill_service(
            db=db,
            bill_id=bill_id,
            deleter_user=current_user,
            group_id=db_bill.group_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting bill {bill_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the bill",
        ) from e


@router.put(
    "/{bill_id}",
    response_model=Bill,
    status_code=status.HTTP_200_OK,
    summary="Update a Bill",
    responses={
        403: {"description": "User not authorized to update this bill or not part of the group"},
        404: {"description": "Group or Bill not found"},
        422: {"description": "Validation Error (e.g., inconsistent bill data in request body)"},
    }
)
async def update_bill_endpoint(
    db: DbSessionDep,
    bill_in: BillUpdate,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(..., ge=1, description="ID of the group the bill belongs to"),
    bill_id: int = Path(..., ge=1, description="ID of the bill to update"),
    _=Depends(validate_group_member),
    __=Depends(authorize_bill_operation),
    bill_to_update: models.Bill = Depends(get_validated_bill_for_group)
):
    """
    Updates a specified bill in a group. Requires the full new bill representation.
    - User must be a member of the group.
    - Bill must belong to the specified group.
    - Bill's creator, Group Owner, or Group Admin can update the bill.
    """
    requester_user_id = current_user.user_id # Assuming current_user.user_id exists
    logger.info(f"User {requester_user_id} attempting to update bill {bill_id} in group {group_id}")

    try:
        # Check bill_in, update and create log
        updated_bill = await update_bill_service(
            db=db,
            bill_to_update=bill_to_update,
            bill_in=bill_in,
            updater_user=current_user,
            group_id=group_id
        )

        final_bill = await get_bill(db=db, bill_id=updated_bill.bill_id)
        if not final_bill:
            logger.error(
                f"CRITICAL: Bill {updated_bill.bill_id} updated by user {requester_user_id} "
                f"but could not be re-fetched for response."
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bill updated but failed to retrieve for response.")

        logger.info(f"User {requester_user_id} successfully updated bill {bill_id} ('{final_bill.title}') in group {group_id}")
        return final_bill

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Unexpected error during update of bill {bill_id} from group {group_id} by user {requester_user_id}: {e}"
        )

        try:
            await db.rollback()
        except Exception as rb_ex:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while trying to update the bill."
        ) from e