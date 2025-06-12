from fastapi import APIRouter, Depends, status, HTTPException, Query, Path
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, ROUND_HALF_UP

import logging

from backend.crud import (
    create_category, get_category, get_category_by_name,
    create_transaction, get_transaction, get_user_transactions,
    get_group, is_member_of_group, get_group_member_ids_and_names,
    calculate_group_net_balances, calculate_suggested_settlements,
    get_users_by_ids, get_user_by_user_id, calculate_balance_between_two_users,
    calculate_all_balances_for_user_in_group
)
import backend.schemas as schemas
from backend.schemas import (
    User, GroupBalanceSummary, UserNetBalance, SettlementSummary, SuggestedPayment, UserBase
)
from backend.database import DbSessionDep
from backend.dependencies import get_current_user, validate_group_member
import backend.models as models
from fastapi_cache.decorator import cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/groups/{group_id}",
    tags=["balances"],
    responses={ # Default responses
        401: {"description": "Not authenticated"},
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group not found"},
        500: {"description": "Internal server error"},
    }
)

@router.get(
    "/balances",
    response_model=GroupBalanceSummary,
)
@cache(expire=300)
async def read_group_balances(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(...),
    _=Depends(validate_group_member),
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve balances for group {group_id}")

    try:
        raw_balances = await calculate_group_net_balances(db=db, group_id=group_id)

        member_schemas = await get_group_member_ids_and_names(db=db, group_id=group_id)
        member_names = {member.user_id: member.username for member in member_schemas}

        user_balance_list: list[UserNetBalance] = []
        for member_id, net_amount in raw_balances.items():
            user_name = member_names.get(member_id, f"User {member_id}")
            user_balance_list.append(
                UserNetBalance(
                    user_id=member_id,
                    username=user_name,
                    net_amount=net_amount
                )
            )

        balance_summary = GroupBalanceSummary(
            group_id=group_id,
            balances=user_balance_list
        )

        logger.info(f"User {user_id} successfully retrieved balances for group {group_id}")
        return balance_summary
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"Unexpected error calculating balances for group {group_id} requested by user {user_id}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred",
        ) from e
    

@router.get(
    "/settlements",
    response_model=SettlementSummary,
    summary="Get Suggested Payments to Settle Group Debts",
    responses={
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group not found"},
    }
)
@cache(expire=300)
async def get_group_settlements(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(...),
    _=Depends(validate_group_member),
):
    user_id = current_user.user_id
    logger.info(f"User {user_id} attempting to retrieve settlement suggestions for group {group_id}")

    try:
        net_balances = await calculate_group_net_balances(db=db, group_id=group_id)
        if not net_balances:
            logger.info(f"No balances found for group {group_id} to calculate settlements.")
            return SettlementSummary(group_id=group_id, suggested_payments=[])

        # Calculate suggested settlement payments using the service function
        settlement_instructions = await calculate_suggested_settlements(
            net_balances=net_balances
        )
        if not settlement_instructions:
            logger.info(f"No settlement payments needed for group {group_id}.")
            return SettlementSummary(group_id=group_id, suggested_payments=[])
        
        # Collect user ids for User nesting
        involved_user_ids = set()
        for instruction in settlement_instructions:
            involved_user_ids.add(instruction.payer_id)
            involved_user_ids.add(instruction.payee_id)
        
        # Fetch the User models for involved users
        users_involved = await get_users_by_ids(db=db, user_ids=list(involved_user_ids))
        user_lookup: dict[int, models.User] = {user.user_id: user for user in users_involved}

        # Add UserBase to SuggestedPayment schema
        suggested_payments: list[SuggestedPayment] = []
        for instruction in settlement_instructions:
            payer_model = user_lookup.get(instruction.payer_id)
            payee_model = user_lookup.get(instruction.payee_id)

            if not payer_model or not payee_model:
                logger.error(
                    f"Data integrity issue: User data not found for payer_id {instruction.payer_id} "
                    f"or payee_id {instruction.payee_id} during settlement calculation for group {group_id}."
                )
                continue 

            payer_details = schemas.User.model_validate(payer_model)
            payee_details = schemas.User.model_validate(payee_model)

            suggested_payments.append(
                SuggestedPayment(
                    payer=payer_details,
                    payee=payee_details,
                    amount=instruction.amount
                )
            )

        # Final response
        settlement_summary = SettlementSummary(
            group_id=group_id,
            suggested_payments=suggested_payments
        )

        logger.info(f"User {user_id} successfully retrieved settlement suggestions for group {group_id}")
        return settlement_summary

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Unexpected error calculating settlements for group {group_id} requested by user {user_id}: {e}"
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while calculating settlement suggestions.",
        ) from e
    

@router.get(
    "/balance_with/{other_user_id}",
    response_model=schemas.UserToUserBalance,
    summary="Get Net Balance Between Current User and Another User",
    responses={
        400: {"description": "Invalid request (e.g., balancing with self, or other user not in group)"},
        403: {"description": "Current user not authorized for this group"},
        404: {"description": "Group or other user not found"},
    }
)
async def get_user_to_user_balance_endpoint( # Renamed for clarity
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user), # ORM model
    group_id: int = Path(..., description="ID of the group"),
    _=Depends(validate_group_member),
    other_user_id: int = Path(...),
):
    is_member = await is_member_of_group(db=db, user_id=other_user_id, group_id=group_id)
    if not is_member:
        logger.warning(f"User {current_user.user_id} forbidden access to group {group_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this group")

    other_user = await get_user_by_user_id(db=db, user_id=other_user_id)

    requester_user_id = current_user.user_id

    if requester_user_id == other_user_id:
        logger.warning(f"User {requester_user_id} attempted to get balance with self in group {group_id}.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot calculate balance with oneself. Please specify a different user."
        )
    
    logger.info(
        f"User {requester_user_id} requesting balance with user {other_user_id} in group {group_id}."
    )

    try:
        # Calculate balance
        precise_balance = await calculate_balance_between_two_users(
            db=db,
            group_id=group_id,
            user1_id=requester_user_id,
            user2_id=other_user_id
        )

        response_data = schemas.UserToUserBalance(
            user1=schemas.User.model_validate(current_user),
            user2=schemas.User.model_validate(other_user),
            group_id=group_id,
            net_amount_user1_owes_user2=precise_balance,
            suggested_settlement_amount=(precise_balance / 1000).quantize(Decimal("0"), rounding=ROUND_HALF_UP) * 1000
        )

        logger.info(
            f"Successfully retrieved balance between user {requester_user_id} and "
            f"user {other_user_id} in group {group_id}: {precise_balance}"
        )
        return response_data

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Unexpected error calculating balance between user {requester_user_id} and "
            f"user {other_user_id} in group {group_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while calculating the bilateral balance.",
        ) from e

@router.get(
    "/balances_with_all_members",
    response_model=list[schemas.SimpleUserBalance],
    summary="Get Net Balances of Current User With All Other Group Members",
    responses={
        403: {"description": "Current user not authorized for this group"},
        404: {"description": "Group not found"},
    }
)
async def get_all_user_to_user_balances_in_group(
    db: DbSessionDep,
    current_user: models.User = Depends(get_current_user),
    group_id: int = Path(..., description="ID of the group"),
    _=Depends(validate_group_member), # Ensures current_user is part of the group
):
    requester_user_id = current_user.user_id
    logger.info(
        f"User {requester_user_id} requesting all their balances with other members in group {group_id}."
    )
    try:
        # This function returns a list of tuples: (models.User, Decimal)
        raw_balances = await calculate_all_balances_for_user_in_group(
            db=db,
            group_id=group_id,
            current_user_id=requester_user_id
        )
        
        # Convert the raw data into the Pydantic response model
        response_balances = [
            schemas.SimpleUserBalance(
                user=schemas.User.model_validate(user_model),
                balance=balance_amount
            )
            for user_model, balance_amount in raw_balances
        ]

        return response_balances
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"Unexpected error calculating all balances for user {requester_user_id} in group {group_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while calculating balances with all members.",
        ) from e