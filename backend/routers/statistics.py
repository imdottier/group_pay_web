from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from typing import List, Dict
from datetime import datetime
from functools import lru_cache
from fastapi_cache.decorator import cache

from backend.schemas import User, SpendingByCategory
from backend.database import DbSessionDep
from backend.dependencies import get_current_user, validate_group_member
from backend.crud import get_spending_by_category_for_group
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/statistics",
    tags=["statistics"],
    dependencies=[Depends(get_current_user)] # Protect all endpoints in this router
)

@router.get(
    "/groups/{group_id}/spending-by-category",
    response_model=List[SpendingByCategory],
    summary="Get monthly spending by category for a group",
    dependencies=[Depends(validate_group_member)] # Ensure user is in group
)
@cache(expire=300)
async def get_group_spending_by_category_endpoint(
    db: DbSessionDep,
    group_id: int = Path(..., description="The ID of the group"),
    year: int = Query(default=datetime.now().year, description="The year to filter by"),
    month: int = Query(default=datetime.now().month, description="The month to filter by (1-12)"),
    include_uncategorized: bool = Query(True, description="Include uncategorized bills?")
):
    """
    Provides a summary of spending grouped by category for a specific group
    and a given month and year.
    """
    logger.info(
        f"Fetching spending by category for group_id={group_id}, year={year}, month={month}, include_uncategorized={include_uncategorized}"
    )
    
    try:
        spending_data = await get_spending_by_category_for_group(
            db=db, group_id=group_id, year=year, month=month, include_uncategorized=include_uncategorized
        )

        # The CRUD function returns a list of tuples. We map it to our Pydantic model.
        return [
            SpendingByCategory(category_name=name, total_amount=amount)
            for name, amount in spending_data
        ]
    
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred while fetching spending stats for group {group_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your request.",
        ) from e 

# --- Monthly Spending Trend Endpoint ---
@router.get(
    "/groups/{group_id}/monthly-spending",
    response_model=Dict[int, float],
    summary="Get monthly spending totals for a group in a given year",
    dependencies=[Depends(validate_group_member)]
)
@cache(expire=300)
async def get_group_monthly_spending(
    db: DbSessionDep,
    group_id: int = Path(..., description="The ID of the group"),
    year: int = Query(default=datetime.now().year, description="The year to filter by"),
    include_uncategorized: bool = Query(True, description="Include uncategorized bills?")
):
    """
    Returns a dictionary mapping month (1-12) to total group spending for each month in the given year.
    """
    logger.info(f"Fetching monthly spending for group_id={group_id}, year={year}, include_uncategorized={include_uncategorized}")
    try:
        monthly_totals = {}
        for month in range(1, 13):
            spending_data = await get_spending_by_category_for_group(
                db=db, group_id=group_id, year=year, month=month, include_uncategorized=include_uncategorized
            )
            total = float(sum(amount for _, amount in spending_data))
            monthly_totals[month] = total
        return monthly_totals
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred while fetching monthly spending for group {group_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your request.",
        ) from e 