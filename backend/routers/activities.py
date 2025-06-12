from fastapi import APIRouter, Depends, status, HTTPException, Query, Path
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, ROUND_HALF_UP

import logging

from backend.crud import (
    create_category, get_category, get_category_by_name,
    create_transaction, get_transaction, get_user_transactions,
    get_group, is_member_of_group, get_group_member_ids_and_names,
    calculate_group_net_balances, calculate_suggested_settlements,
    get_users_by_ids, get_user_by_user_id, calculate_balance_between_two_users
)
import backend.schemas as schemas
from backend.schemas import (
    User, GroupBalanceSummary, UserNetBalance, SettlementSummary, SuggestedPayment, UserBase
)
from backend.database import DbSessionDep
from backend.dependencies import get_current_user, validate_group_member
import backend.models as models

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/groups/{group_id}/activity",
    tags=["activities"],
    responses={ # Default responses
        401: {"description": "Not authenticated"},
        403: {"description": "User not authorized for this group"},
        404: {"description": "Group not found"},
        500: {"description": "Internal server error"},
    }
)
