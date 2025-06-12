from typing import Annotated
from fastapi import Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from fastapi.security import HTTPAuthorizationCredentials

# Import necessary components FROM OTHER MODULES
from backend.security import SECRET_KEY, ALGORITHM, oauth2_scheme, bearer_scheme # Import JWT stuff & scheme
from backend.database import DbSessionDep # Import DB dependency alias
from backend.crud import (
    get_user_by_user_id, get_group, is_member_of_group, validate_member_ids_in_group,
    get_bill, get_user_role_in_group, get_payment
)
from backend.schemas import TokenData, User, BillCreate, BillUpdate
from backend.models import SplitMethod, Bill, GroupRole, Payment
import logging

logger = logging.getLogger(__name__)


# async def get_current_user(
#     token: Annotated[str, Depends(oauth2_scheme)],
#     db: DbSessionDep,
# ):
async def get_current_user(
    # Depend on HTTPBearer to extract credentials from header
    http_auth: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: DbSessionDep,
):
    # credentials_exception = HTTPException(
    #     status_code=status.HTTP_401_UNAUTHORIZED,
    #     detail="Invalid authentication credentials",
    #     headers={"WWW-Authenticate": "Bearer"}
    # )
    # try:
    #     payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    #     subject = payload.get("sub")
    #     if subject is None:
    #         raise credentials_exception
    #     token_data = TokenData(subject=subject)
    # except JWTError as e:
    #     print(f"JWTError: {e}")
    #     raise credentials_exception from e
    
    # user = await get_user_by_user_id(db=db, user_id=int(token_data.subject))
    # if user is None:
    #     print(f"User not found for subject: {token_data.subject}")
    #     raise credentials_exception
    # return user
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}, # Important: Specify Bearer scheme here
    )

    # Check if auth credentials were provided and scheme is Bearer
    if http_auth is None or http_auth.scheme.lower() != "bearer":
        raise credentials_exception

    token = http_auth.credentials # Get the token string

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject: str | None = payload.get("sub")
        if subject is None:
            raise credentials_exception
        token_data = TokenData(subject=subject)
    except JWTError:
        # Catch JWT specific errors (expired, invalid signature etc)
        raise credentials_exception

    try:
        user_id = int(token_data.subject)
    except (ValueError, TypeError): # Catch if subject is not a number string
        raise credentials_exception

    user = await get_user_by_user_id(db, user_id=user_id)
    if user is None:
        raise credentials_exception
    return user


async def validate_group_member(
    db: DbSessionDep,
    current_user: User = Depends(get_current_user),
    group_id: int = Path(...),
):
    db_group = await get_group(db=db, group_id=group_id)
    if db_group is None:
        logger.warning(f"Group {group_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    is_member = await is_member_of_group(db=db, user_id=current_user.user_id, group_id=group_id)
    if not is_member:
        logger.warning(f"User {current_user.user_id} forbidden access to group {group_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this group")
        

async def get_validated_bill_for_group(
    db: DbSessionDep,
    bill_id: int = Path(..., description="The ID of the bill"),
    group_id: int = Path(..., description="The ID of the group from the path"),
) -> Bill:
    db_bill = await get_bill(db=db, bill_id=bill_id)
    if not db_bill:
        logger.warning(f"Validation failed: Bill {bill_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")

    if db_bill.group_id != group_id:
        logger.warning(
            f"Validation failed: Bill {bill_id} belongs to group {db_bill.group_id}, "
            f"but access was attempted via group path {group_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill does not belong to the specified group or was not found."
        )
    return db_bill


# Check if user is in group and has authority to modify a specific bill
async def authorize_bill_operation(
    db: DbSessionDep,
    db_bill: Bill = Depends(get_validated_bill_for_group),
    current_user: User = Depends(get_current_user),
) -> None:
    requester_user_id = current_user.user_id
    bill_group_id = db_bill.group_id

    # Check if user is in group
    requester_role = await get_user_role_in_group(
        db=db, user_id=requester_user_id, group_id=bill_group_id
    )

    if requester_role is None:
        logger.warning(
            f"Authorization failed for bill {db_bill.bill_id}: User {requester_user_id} "
            f"not found or has no role in bill's group {bill_group_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized for the bill's group or role indeterminate."
        )

    # Authorization Check: Bill creator or owner/admin can modify bill
    is_bill_creator = (db_bill.created_by == requester_user_id)
    is_group_owner_or_admin = requester_role in {
        GroupRole.owner,
        GroupRole.admin
    }

    if not (is_bill_creator or is_group_owner_or_admin):
        logger.warning(
            f"Authorization failed for bill {db_bill.bill_id}: User {requester_user_id} "
            f"(role: {requester_role.value if hasattr(requester_role, 'value') else requester_role}) "
            f"is not bill creator ({db_bill.created_by}) nor group owner/admin."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this operation on the bill."
        )
    

async def get_validated_payment_for_group(
    db: DbSessionDep,
    payment_id: int = Path(..., description="The ID of the bill"),
    group_id: int = Path(..., description="The ID of the group from the path"),
) -> Payment:
    db_payment = await get_payment(db=db, payment_id=payment_id, group_id=group_id)
    if not db_payment:
        logger.warning(f"Validation failed: Payment{payment_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if db_payment.group_id != group_id:
        logger.warning(
            f"Validation failed: Payment{payment_id} belongs to group {db_payment.group_id}, "
            f"but access was attempted via group path {group_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment does not belong to the specified group or was not found."
        )
    return db_payment


async def authorize_payment_operation(
    db: DbSessionDep,
    db_payment: Payment = Depends(get_validated_payment_for_group),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Authorizes if the current user can perform an operation (e.g., delete) on the given payment.
    Checks if:
    1. The user is a member of the payment's group and has a role.
    2. The user is the payment's Payer OR a group owner/admin of the payment's group.

    Assumes db_payment is already validated for existence and its group_id matches path group_id.
    """
    requester_user_id = current_user.user_id
    payment_actual_group_id = db_payment.group_id

    # Check user is in group
    requester_role = await get_user_role_in_group(
        db=db, user_id=requester_user_id, group_id=payment_actual_group_id
    )

    if requester_role is None:
        logger.warning(
            f"Authorization failed for payment {db_payment.payment_id}: User {requester_user_id} "
            f"not found or has no role in payment's group {payment_actual_group_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized for the payment's group or role indeterminate."
        )

    # Authorization Check: Payment Payer OR Group Owner/Admin
    is_payment_payer = (db_payment.payer_id == requester_user_id)
    is_group_owner_or_admin = requester_role in {
        GroupRole.owner, 
        GroupRole.admin
    }

    if not (is_payment_payer or is_group_owner_or_admin):
        logger.warning(
            f"Authorization failed for payment {db_payment.payment_id}: User {requester_user_id} "
            f"(role: {requester_role.value if hasattr(requester_role, 'value') else requester_role}) "
            f"is not payment payer ({db_payment.payer_id}) nor group owner/admin."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this operation on the payment."
        )