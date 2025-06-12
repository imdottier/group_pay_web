from fastapi import APIRouter, Depends, status, HTTPException, Path
from sqlalchemy.exc import IntegrityError
import logging

from backend.crud import (
    get_group, is_member_of_group,
    create_bill, validate_member_ids_in_group,
    get_bill, get_group_bills,
    create_payment,
    create_category, get_category, get_user_categories
)
from backend.schemas import (
    User, TransactionCategory, TransactionCategoryCreate
)
from backend.database import DbSessionDep
from backend.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/categories",
    tags=["transaction-categories"],
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    }
)

@router.post(
    "/",
    response_model=TransactionCategory,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Category with this name already exists for the user"},
        422: {"description": "Validation Error (e.g., name too short/long)"},
    }
)
async def create_new_category(
    category_in: TransactionCategoryCreate,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to create category with name: '{category_in.name}'")

    try:
        db_category = await create_category(
            db=db,
            category_in=category_in,
            user_id=user_id
        )
        logger.info(
            f"User {user_id} successfully created category '{db_category.name}'"
            f"(ID: {db_category.category_id})"
        )
        return db_category

    except IntegrityError as e:
        logger.warning(
            f"IntegrityError (likely duplicate name) for user {user_id} creating category '{category_in.name}': {e}"
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A category with the name '{category_in.name}' already exists.",
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Unexpected error creating category for user {user_id} with name '{category_in.name}'"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the category.",
        ) from e
    

@router.get(
    "/",
    response_model=list[TransactionCategory]
)
async def read_user_categories_endpoint(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve their categories.")

    try:
        categories = await get_user_categories(db=db, user_id=user_id)
        logger.info(f"User {user_id} successfully retrieved {len(categories)} categories.")
        return categories

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error retrieving categories for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving categories.",
        ) from e


@router.get(
    "/{category_id}",
    response_model=TransactionCategory,
    responses={
        404: {"description": "Category not found or not owned by user"},
    }
)
async def read_category_endpoint(
    category_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve category {category_id}.")

    try:
        category = await get_category(db=db, category_id=category_id, user_id=user_id)

        if category is None:
            logger.warning(f"Category {category_id} not found or not owned by user {user_id}.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        logger.info(f"User {user_id} successfully retrieved category '{category.name}' (ID: {category_id}).")
        return category

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error retrieving category {category_id} for user {user_id}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the category.",
        ) from e