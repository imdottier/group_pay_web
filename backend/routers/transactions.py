from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.exc import IntegrityError
import logging

from backend.crud import (
    create_category, get_category, get_category_by_name,
    create_transaction, get_transaction, get_user_transactions,
    update_transaction, delete_transaction, get_category_by_id,
)
from backend.schemas import (
    User, Transaction, TransactionCreate, NewCategory, ExistingCategory, TransactionCategoryCreate,
    TransactionUpdate,
)
from backend.database import DbSessionDep
from backend.dependencies import get_current_user

logger = logging.getLogger(__name__)

# Define the router (ensure this file is included in main.py)
router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    responses={ # Default responses
        401: {"description": "Not authenticated"},
        400: {"description": "Bad Request (e.g., invalid category ID)"},
        404: {"description": "Not found"},
        409: {"description": "Conflict (e.g., category name already exists)"},
        422: {"description": "Validation Error (schema level)"},
        500: {"description": "Internal server error"},
    }
)

@router.post(
    "/",
    response_model=Transaction,
    status_code=status.HTTP_201_CREATED
)
async def create_new_transaction(
    transaction_in: TransactionCreate,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.user_id
    logger.info(
        f"User {user_id} attempting to create transaction"
        f"with amount {transaction_in.amount}"
    )

    category_id_to_use: int

    try:
        # Try to create new category
        if isinstance(transaction_in.category_input, NewCategory):
            category_name = transaction_in.category_input.name
            logger.info(f"Transaction input specifies new category: '{category_name}'")

            # Check if category already exists
            existing_category = await get_category_by_name(db=db, name=category_name, user_id=user_id)
            if existing_category:
                category_id_to_use = existing_category.category_id
                logger.info(f"Category '{category_name}' already exists (ID: {category_id_to_use}), using existing.")
            else:
                # Try to create the new category
                try:
                    new_category_schema = TransactionCategoryCreate(name=category_name)
                    created_category = await create_category(
                        db=db, category_in=new_category_schema, user_id=user_id
                    )
                    category_id_to_use = created_category.category_id
                    logger.info(f"Successfully created new category '{created_category.name}' (ID: {category_id_to_use})")
                
                except IntegrityError:
                    logger.warning(
                        f"IntegrityError (likely race) creating category '{category_name}' for user {user_id}."
                        f"Assuming it exists."
                    )

                    refetched_category = await get_category_by_name(db=db, name=category_name, user_id=user_id)
                    if not refetched_category:
                        raise HTTPException(
                            status_code=500, 
                            detail="Error resolving category after conflict."
                        )
                    category_id_to_use = refetched_category.category_id

        # Try to find existing category
        elif isinstance(transaction_in.category_input, ExistingCategory):
            category_id_to_use = transaction_in.category_input.category_id
            logger.info(f"Transaction input specifies existing category ID: {category_id_to_use}")
            
            category = await get_category(db=db, category_id=category_id_to_use, user_id=user_id)
            if category is None:
                logger.warning(f"Invalid or unauthorized category_id {category_id_to_use} provided by user {user_id}.")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID provided.")
        
        else:
            logger.error(f"Invalid category_input type received: {type(transaction_in.category_input)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid category input structure."
            )

        db_transaction = await create_transaction(
            db=db,
            transaction_data=transaction_in,
            user_id=user_id,
            category_id=category_id_to_use,
        )

        logger.info(f"User {user_id} successfully created transaction {db_transaction.transaction_id}")


        final_transaction = await get_transaction(
            db=db, transaction_id=db_transaction.transaction_id, user_id=user_id
        )
        if not final_transaction:
            logger.error(f"Could not retrieve newly created transaction {db_transaction.transaction_id} for response.")
            return db_transaction
        return final_transaction


    except IntegrityError as e:
        logger.warning(f"IntegrityError during final transaction creation for user {user_id}: {e}")

        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after transaction IntegrityError: {rollback_err}")
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create transaction due to data conflict or invalid category reference.",
        ) from e

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error during transaction creation for user {user_id}")

        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after unexpected transaction error: {rollback_err}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the transaction.",
        ) from e
    

@router.get(
    "/{transaction_id}",
    response_model=Transaction,
    responses={
        404: {"description": "Transaction not found or not owned by user"},
    },
)
async def read_transaction(
    transaction_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve transaction {transaction_id}.")

    try:
        # log
        db_transaction = await get_transaction(
            db=db,
            transaction_id=transaction_id,
            user_id=user_id
        )

        if db_transaction is None:
            logger.warning(f"Transaction {transaction_id} not found or not owned by user {user_id}.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        logger.info(f"User {user_id} successfully retrieved transaction {transaction_id}.")
        return db_transaction

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error retrieving transaction {transaction_id} for user {user_id}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred",
        ) from e
    

@router.get(
    "/",
    response_model=list[Transaction]
)
async def read_user_transactions(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of records to return")
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve their transactions (skip={skip}, limit={limit}).")

    try:
        transactions = await get_user_transactions(
            db=db,
            user_id=user_id,
            skip=skip,
            limit=limit
        )

        logger.info(f"User {user_id} successfully retrieved {len(transactions)} transactions.")
        return transactions

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error retrieving transactions for user {user_id}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving transactions.",
        ) from e

@router.put(
    "/{transaction_id}",
    response_model=Transaction,
    responses={
        404: {"description": "Transaction not found or not owned by user"},
        400: {"description": "Bad request (e.g., invalid category)"},
    }
)
async def update_user_transaction(
    transaction_id: int,
    transaction_in: TransactionUpdate,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    """
    Update a specific transaction owned by the current user.
    """
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to update transaction {transaction_id}")

    try:
        # First get the existing transaction
        db_transaction = await get_transaction(db=db, transaction_id=transaction_id, user_id=user_id)
        if not db_transaction:
            logger.warning(f"Transaction {transaction_id} not found or not owned by user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        # Handle category update if provided
        category_id_to_use = None
        if transaction_in.category_input:
            if isinstance(transaction_in.category_input, NewCategory):
                category_name = transaction_in.category_input.name
                logger.info(f"Update specifies new category: '{category_name}'")

                # Check if category already exists
                existing_category = await get_category_by_name(db=db, name=category_name, user_id=user_id)
                if existing_category:
                    category_id_to_use = existing_category.category_id
                    logger.info(f"Category '{category_name}' already exists (ID: {category_id_to_use}), using existing")
                else:
                    # Create new category
                    try:
                        new_category_schema = TransactionCategoryCreate(name=category_name)
                        created_category = await create_category(
                            db=db, category_in=new_category_schema, user_id=user_id
                        )
                        category_id_to_use = created_category.category_id
                        logger.info(f"Created new category '{created_category.name}' (ID: {category_id_to_use})")
                    except IntegrityError:
                        logger.warning(f"Race condition creating category '{category_name}', attempting to fetch existing")
                        refetched_category = await get_category_by_name(db=db, name=category_name, user_id=user_id)
                        if not refetched_category:
                            raise HTTPException(
                                status_code=500,
                                detail="Error resolving category after conflict"
                            )
                        category_id_to_use = refetched_category.category_id

            elif isinstance(transaction_in.category_input, ExistingCategory):
                category_id_to_use = transaction_in.category_input.category_id
                logger.info(f"Update specifies existing category ID: {category_id_to_use}")
                
                # Verify category exists and belongs to user
                category = await get_category_by_id(db=db, category_id=category_id_to_use, user_id=user_id)
                if not category:
                    logger.warning(f"Invalid category_id {category_id_to_use} provided by user {user_id}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid category ID provided"
                    )

        # Update the transaction
        try:
            updated_transaction = await update_transaction(
                db=db,
                db_transaction=db_transaction,
                transaction_update=transaction_in,
                category_id=category_id_to_use
            )
            await db.commit()
            logger.info(f"Successfully updated transaction {transaction_id}")
            return updated_transaction

        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"IntegrityError updating transaction {transaction_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update transaction due to data conflict"
            ) from e

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error updating transaction {transaction_id}")
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after unexpected transaction error: {rollback_err}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the transaction"
        ) from e


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Transaction not found or not owned by user"},
    }
)
async def delete_user_transaction(
    transaction_id: int,
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a specific transaction owned by the current user.
    """
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to delete transaction {transaction_id}")

    try:
        # Attempt to delete the transaction
        deleted = await delete_transaction(db=db, transaction_id=transaction_id, user_id=user_id)
        
        if not deleted:
            logger.warning(f"Transaction {transaction_id} not found or not owned by user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        await db.commit()
        logger.info(f"Successfully deleted transaction {transaction_id}")
        return None  # 204 No Content

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error deleting transaction {transaction_id}")
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.error(f"Error during rollback after transaction delete error: {rollback_err}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the transaction"
        ) from e