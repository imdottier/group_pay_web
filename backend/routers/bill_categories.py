from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
import logging

from backend import crud, schemas
from backend.database import DbSessionDep
from backend.dependencies import get_current_user, validate_group_member

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/bill_categories",
    tags=["bill-categories"],
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    }
)

@router.get(
    "/group/{group_id}",
    response_model=list[schemas.BillCategory],
    dependencies=[Depends(validate_group_member)], # Ensures user is part of the group
)
async def read_bill_categories_for_group(
    group_id: int,
    db: DbSessionDep,
    current_user: schemas.User = Depends(get_current_user),
):
    """
    Get all bill categories for a specific group, including default categories.
    The user must be a member of the group to access this endpoint.
    """
    logger.info(f"User {current_user.user_id} retrieving bill categories for group {group_id}")
    try:
        categories = await crud.get_bill_categories_for_group(db, group_id=group_id)
        logger.info(f"Found {len(categories)} categories for group {group_id}")
        return categories
    except Exception as e:
        logger.exception(f"Error retrieving bill categories for group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving bill categories."
        ) 