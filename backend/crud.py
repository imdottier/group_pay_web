from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, func, or_, delete, update, extract, desc
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload
import logging

from typing import Optional, Union
from decimal import Decimal, ROUND_HALF_UP

import backend.models as models
from backend.models import (
    SplitMethod, NotificationType,
    User, Group, GroupMember, GroupRole, Bill, BillCategory,
    InitialPayment, BillItem, BillPart, BillItemSplit,
    Payment, TransactionCategory, Transaction, Notification,
    AuditActionType, Friendship, FriendshipStatus, GroupInvitation, GroupInvitationStatus
)
import backend.schemas as schemas
from backend.schemas import UserBase, UserCreate, GroupCreate, BillCreate, PaymentCreate, TransactionCategoryCreate, TransactionCreate, SuggestedPayment, TransactionCategoryUpdate, FriendshipCreate, FriendshipUpdate, GroupInvitationCreate, GroupInvitationUpdate, BillUpdate
from backend.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)

async def _get_or_create_bill_category(db: AsyncSession, category_input: Optional[Union[schemas.ExistingBillCategory, schemas.NewBillCategory]], group_id: int) -> Optional[int]:
    """Helper to get or create a bill category."""
    if category_input is None:
        return None

    if isinstance(category_input, schemas.NewBillCategory):
        # Check if a category with this name already exists for the group
        stmt = select(models.BillCategory).filter_by(name=category_input.name, group_id=group_id)
        result = await db.execute(stmt)
        existing_category = result.scalars().first()
        if existing_category:
            return existing_category.category_id

        # Create a new one
        db_category = models.BillCategory(name=category_input.name, group_id=group_id)
        db.add(db_category)
        await db.flush()  # To get the new category_id
        return db_category.category_id
    
    elif isinstance(category_input, schemas.ExistingBillCategory):
        # Optional: Verify the category_id belongs to the group or is a default one
        stmt = select(models.BillCategory).filter_by(category_id=category_input.category_id).filter(
            or_(models.BillCategory.group_id == group_id, models.BillCategory.group_id == None)
        )
        result = await db.execute(stmt)
        if not result.scalars().first():
            raise ValueError(f"Category ID {category_input.category_id} not found for group {group_id}")
        return category_input.category_id
    
    return None


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalars().first()
    return user


async def get_user_by_user_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).filter(User.user_id == user_id))
    return result.scalars().first()


async def search_users(db: AsyncSession, query: str, current_user_id: int, limit: int = 10) -> list[User]:
    """
    Search for users by username or email, excluding the current user.
    """
    search_query = f"%{query}%"
    stmt = (
        select(User)
        .filter(
            or_(
                User.username.ilike(search_query),
                User.email.ilike(search_query)
            ),
            User.user_id != current_user_id
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()
    return users


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    hashed_password = get_password_hash(user.password)

    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password
    )

    try:
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user

    except IntegrityError as e:
        # Likely duplicate email or username
        try:
            await db.rollback()
        except Exception:
            pass # Ignore rollback error
        raise e # Re-raise original IntegrityError

    except SQLAlchemyError as e:
        # Other potential DB errors during commit/refresh
        try:
            await db.rollback()
        except Exception:
            pass # Ignore rollback error
        raise e # Re-raise original SQLAlchemyError

    except Exception as e:
        # Any other unexpected error
        try:
            await db.rollback()
        except Exception:
            pass # Ignore rollback error
        raise e


async def authenticate_user(db: AsyncSession, identifier: str, password: str) -> User | None:    
    # Try finding user by email first
    user = await get_user_by_email(db, email=identifier)

    # If not found by email, try by username
    if user is None:
        user = await get_user_by_username(db, username=identifier)

    # If no user found by either identifier, authentication fails
    if user is None:
        return None

    # If user found, check the password (ensure user has a password set)
    if not user.hashed_password or not verify_password(password, user.hashed_password):
        return None # Password incorrect or not set (e.g., OAuth user)

    # If user found and password is correct
    return user 


# Group
async def create_group(db: AsyncSession, group_in: GroupCreate, creator_id: int) -> Group:
    db_group = Group(
        group_name=group_in.group_name,
        description=group_in.description
    )

    db.add(db_group)
    try:
        # Flush to get the group_id before adding the member
        await db.flush()

        # Create the GroupMember instance
        db_member = GroupMember(
            group_id=db_group.group_id,
            user_id=creator_id,
            role=GroupRole.owner
        )
        db.add(db_member)

        # Refresh the group instance after successful commit
        await db.refresh(db_group)
        return db_group
    except SQLAlchemyError as e:
        raise e



async def get_group(db: AsyncSession, group_id: int) -> Group | None:
    stmt = (
        select(models.Group)
        .where(models.Group.group_id == group_id)
        .options(
            selectinload(models.Group.members)
                .joinedload(models.GroupMember.user),
            selectinload(models.Group.bill_categories)
        )
    )
   
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_bill_categories_for_group(db: AsyncSession, group_id: int) -> list[models.BillCategory]:
    """
    Retrieves all bill categories for a specific group, including default categories.
    Default categories are those where group_id is NULL.
    """
    stmt = (
        select(models.BillCategory)
        .filter(or_(models.BillCategory.group_id == group_id, models.BillCategory.group_id == None))
        .order_by(models.BillCategory.name)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_user_groups(db: AsyncSession, user_id: int) -> list[Group] | None:
    stmt = (
        select(Group)
        .join(GroupMember, Group.group_id == GroupMember.group_id)
        .where(GroupMember.user_id == user_id)
        .options(
            selectinload(models.Group.members)
                .joinedload(models.GroupMember.user),
            selectinload(models.Group.bill_categories)
        )
    )

    result = await db.execute(stmt)
    return result.scalars().unique().all()


async def get_group_member_with_user(
    db: AsyncSession,
    group_id: int,
    user_id: int
) -> Optional[GroupMember]:
    """
    Retrieves a specific group membership record, eagerly loading the related User.
    """
    stmt = (
        select(GroupMember)
        .where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
        .options(
            selectinload(GroupMember.user)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_group_members(db: AsyncSession, group_id: int) -> list[GroupMember]:
    stmt = (
        select(GroupMember)
        .where(GroupMember.group_id == group_id, GroupMember.left_at == None)
        .options(
            selectinload(GroupMember.user)
        )
    )

    result = await db.execute(stmt)
    return result.scalars().all()


async def add_user_to_group(
    db: AsyncSession, group_id: int, user_id: int, role: GroupRole
) -> GroupMember:
    db_member = GroupMember(
        group_id=group_id,
        user_id=user_id,
        role=role
    )
    db.add(db_member)
    
    try:
        await db.flush()
        await db.refresh(db_member)
    
    except SQLAlchemyError as e:
        raise e

    return db_member
    

async def is_member_of_group(
    db: AsyncSession, user_id: int, group_id: int
) -> bool:
    stmt = (
        select(GroupMember)
        .where(
            GroupMember.user_id == user_id,
            GroupMember.group_id == group_id
        )
    )

    exists_stmt = select(exists(stmt))
    result = await db.execute(exists_stmt)
    return result.scalar_one()


async def get_user_role_in_group(
    db: AsyncSession, user_id: int, group_id: int
) -> GroupRole | None:
    stmt = (
        select(GroupMember.role)
        .where(
            GroupMember.user_id == user_id,
            GroupMember.group_id == group_id
        )
    )

    result = await db.execute(stmt)
    return result.scalars().first()


async def remove_user_from_group(db: AsyncSession, group_id: int, user_id_to_remove: int) -> bool:
    """
    Removes a specific user from a specific group by deleting the GroupMember record.
    Returns True if a record was deleted, False otherwise. (No Logging)

    Raises:
        SQLAlchemyError: For database errors during delete/commit.
        Exception: For other unexpected errors.
    """
    stmt = (
        delete(GroupMember)
        .where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id_to_remove
        )
    )

    try:
        result = await db.execute(stmt)
        was_deleted = result.rowcount is not None and result.rowcount > 0
        return was_deleted

    except SQLAlchemyError as e:
        # Let the router handle rollback
        raise e
    except Exception as e:
        # Let the router handle rollback
        raise e


async def create_bill(
    db: AsyncSession, bill_in: BillCreate,  creator_id: int, group_id: int
) -> Bill:
    """
    Creates a new bill, its initial payments, items, and splits in the database
    within a single transaction.
    """
    # --- 1. Resolve Category ---
    try:
        category_id = await _get_or_create_bill_category(db, bill_in.category_input, group_id)
    except ValueError as e:
        raise e

    # --- 2. Create the Bill ---
    db_bill = Bill(
        group_id=group_id,
        created_by=creator_id,
        title=bill_in.title,
        description=bill_in.description,
        total_amount=bill_in.total_amount,
        split_method=bill_in.split_method,
        category_id=category_id, # Use resolved category_id
        receipt_image_url=bill_in.receipt_image_url,
    )
    db.add(db_bill)
    # Flush to get the bill_id for relationships
    await db.flush()

    try:
        await db.flush()

        if db_bill.bill_id is None:
            try:
                await db.rollback()
            except Exception:
                pass
            raise ValueError("Failed to obtain bill_id after flush during bill creation.")

        for initial_payment in bill_in.initial_payments:
            db_initial_payment = InitialPayment(
                bill_id=db_bill.bill_id,
                user_id=initial_payment.user_id,
                amount_paid=initial_payment.amount_paid
            )
            db.add(db_initial_payment)

        item_id_counter = 1
        for item in bill_in.items:
            db_item = BillItem(
                bill_id=db_bill.bill_id,
                item_id=item_id_counter,
                name=item.name,
                unit_price=item.unit_price,
                quantity=item.quantity,
            )
            db.add(db_item)

            if bill_in.split_method == SplitMethod.item:
                for split_data in item.splits:
                    db_item_split = BillItemSplit(
                        bill_id=db_bill.bill_id,
                        item_id=item_id_counter,
                        user_id=split_data.user_id,
                        quantity=split_data.quantity
                    )
                    db.add(db_item_split)

            item_id_counter += 1
        

        if bill_in.split_method == SplitMethod.exact:
            for bill_part in bill_in.bill_parts:
                db_bill_part = BillPart(
                    bill_id=db_bill.bill_id,
                    user_id=bill_part.user_id,
                    amount_owed=bill_part.amount_owed,
                )
                db.add(db_bill_part)

        elif bill_in.split_method == SplitMethod.equal:
            members = await get_group_member_ids_and_names(db=db, group_id=group_id)
            current_member_ids = [member.user_id for member in members]

            if current_member_ids:
                num_members = len(current_member_ids)
                if num_members > 0:
                    bill_total_amount = bill_in.total_amount
                    
                    # Calculate base share and remainder
                    base_share = bill_total_amount // num_members
                    remainder = bill_total_amount % num_members
                    
                    # Distribute base share and remainder
                    for i, member_user_id in enumerate(current_member_ids):
                        share = base_share
                        if i < remainder:
                            share += 1 # Distribute the remainder 1 VND at a time
                        
                        db_bill_part = BillPart(
                            bill_id=db_bill.bill_id,
                            user_id=member_user_id,
                            amount_owed=share
                        )
                        db.add(db_bill_part)

        await db.refresh(db_bill, attribute_names=["initial_payments", "items", "bill_parts", "bill_creator", "group"])
        return db_bill
        
    except IntegrityError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    
    except SQLAlchemyError as e:
        # Other potential DB errors during commit/refresh
        try:
            await db.rollback()
        except Exception:
            pass # Ignore rollback error
        raise e # Re-raise original SQLAlchemyError

    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    

async def validate_member_ids_in_group(db: AsyncSession, *, user_ids: list[int], group_id: int) -> bool:
    """Checks if all provided user_ids are members of the specified group."""
    if not user_ids:
        return True

    stmt = (
        select(func.count(GroupMember.user_id))
        .where(
            GroupMember.group_id == group_id,
            GroupMember.user_id.in_(user_ids)
        )
    )
    result = await db.execute(stmt)
    count = result.scalar_one_or_none()

    return count == len(set(user_ids))


async def get_bill(db: AsyncSession, bill_id: int) -> Bill | None:
    stmt = (
        select(models.Bill)
        .where(models.Bill.bill_id == bill_id)
        .options(
            selectinload(models.Bill.initial_payments).selectinload(models.InitialPayment.user),
            selectinload(models.Bill.items).selectinload(models.BillItem.bill_item_splits).selectinload(models.BillItemSplit.user),
            selectinload(models.Bill.bill_parts).selectinload(models.BillPart.user),
            selectinload(models.Bill.bill_creator),
            selectinload(models.Bill.category)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_group_bills(db: AsyncSession, group_id: int, skip: int = 0, limit: int = 10) -> list[Bill]:
    """
    Retrieves all bills for a given group with their initial payments, parts, and related user details.
    """
    stmt = (
        select(models.Bill)
        .where(models.Bill.group_id == group_id)
        .options(
            selectinload(models.Bill.initial_payments).selectinload(models.InitialPayment.user),
            selectinload(models.Bill.items).selectinload(models.BillItem.bill_item_splits).selectinload(models.BillItemSplit.user),
            selectinload(models.Bill.bill_parts).selectinload(models.BillPart.user),
            selectinload(models.Bill.bill_creator),
            selectinload(models.Bill.category)
        )
        .order_by(models.Bill.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    bills = result.scalars().unique().all()
    return bills


async def delete_bill(db: AsyncSession, bill_id: int) -> bool:
    """
    Removes a specific bill from the database by its ID.
    Returns True if the bill record was deleted, False otherwise.

    Raises:
        SQLAlchemyError: For database errors during delete/commit.
        Exception: For other unexpected errors.
    """
    stmt = (
        delete(Bill)
        .where(Bill.bill_id == bill_id)
    )

    try:
        result = await db.execute(stmt)
        await db.commit()

        was_deleted = result.rowcount is not None and result.rowcount > 0
        return was_deleted

    except SQLAlchemyError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    

async def update_bill(
    db: AsyncSession,
    db_bill: Bill, # The existing bill object from DB
    bill_in: BillUpdate # The validated update data
) -> Optional[Bill]:
    """
    Updates an existing bill. This function is complex due to the need to handle
    updates to nested relationships (payments, items, splits) correctly.
    The approach is to remove old related objects and create new ones based on `bill_in`.
    """
    
    # --- 1. Resolve Category ---
    try:
        category_id = await _get_or_create_bill_category(db, bill_in.category_input, db_bill.group_id)
    except ValueError as e:
        raise e # Propagate error if category is invalid

    # --- 2. Update Bill's Top-Level Fields ---
    db_bill.title = bill_in.title
    db_bill.description = bill_in.description
    db_bill.total_amount = bill_in.total_amount
    db_bill.split_method = bill_in.split_method
    db_bill.category_id = category_id
    
    # --- 3. Clear Existing Collections ---
    # Delete existing bill parts if any
    await db.execute(delete(InitialPayment).where(InitialPayment.bill_id == db_bill.bill_id))
    await db.execute(delete(BillItem).where(BillItem.bill_id == db_bill.bill_id))
    await db.execute(delete(BillPart).where(BillPart.bill_id == db_bill.bill_id))
    
    await db.flush()

    # Recreate initial_payments, items, and bill_parts
    for initial_payment in bill_in.initial_payments:
        db_initial_payment = InitialPayment(
            bill_id=db_bill.bill_id,
            user_id=initial_payment.user_id,
            amount_paid=initial_payment.amount_paid
        )
        db.add(db_initial_payment)

    item_id_counter = 1
    for item in bill_in.items:
        db_item = BillItem(
            bill_id=db_bill.bill_id,
            item_id=item_id_counter,
            name=item.name,
            unit_price=item.unit_price,
            quantity=item.quantity,
        )
        db.add(db_item)

        if bill_in.split_method == SplitMethod.item:
            for split_data in item.splits:
                db_item_split = BillItemSplit(
                    bill_id=db_bill.bill_id,
                    item_id=item_id_counter,
                    user_id=split_data.user_id,
                    quantity=split_data.quantity
                )
                db.add(db_item_split)

        item_id_counter += 1
    

    if bill_in.split_method == SplitMethod.exact:
        for bill_part in bill_in.bill_parts:
            db_bill_part = BillPart(
                bill_id=db_bill.bill_id,
                user_id=bill_part.user_id,
                amount_owed=bill_part.amount_owed,
            )
            db.add(db_bill_part)

    elif bill_in.split_method == SplitMethod.equal:
        members = await get_group_member_ids_and_names(db=db, group_id=db_bill.group_id)
        current_member_ids = [member.user_id for member in members]
        if current_member_ids:
            num_members = len(current_member_ids)
            if num_members > 0:
                base_share = bill_in.total_amount // num_members
                remainder = bill_in.total_amount % num_members
                for i, member_user_id in enumerate(current_member_ids):
                    share = base_share
                    if i < remainder:
                        share += 1
                    db_bill_part = BillPart(
                        bill_id=db_bill.bill_id,
                        user_id=member_user_id,
                        amount_owed=share
                    )
                    db.add(db_bill_part)

    await db.refresh(db_bill, attribute_names=["initial_payments", "items", "bill_parts", "bill_creator", "group"])
    return db_bill


async def create_payment(db: AsyncSession, payment_in: PaymentCreate, creator_id: int, group_id: int) -> Payment:
    db_payment = Payment(
        group_id=group_id,
        payer_id=creator_id,
        payee_id=payment_in.payee_id,
        bill_id=payment_in.bill_id,
        notes=payment_in.notes,
        amount=payment_in.amount,
        payment_date=payment_in.payment_date,
    )
    db.add(db_payment)

    try:
        await db.flush()
        await db.refresh(db_payment, attribute_names=['payment_id'])
    except SQLAlchemyError as e:
        raise e

    return db_payment
    

async def get_payment(
    db: AsyncSession, payment_id: int, group_id: int,
) -> Payment | None:
    stmt = (
        select(Payment)
        .where(
            Payment.payment_id == payment_id,
            Payment.group_id == group_id,
        )
        .options(
            joinedload(Payment.payer),
            joinedload(Payment.payee)
        )
    )

    result = await db.execute(stmt)
    return result.scalars().first()


async def delete_payment(db: AsyncSession, payment_id: int) -> bool:
    """
    Deletes a specific payment from the database by its ID.
    Returns True if the payment record was deleted, False otherwise.

    Raises:
        SQLAlchemyError: For database errors during delete/commit.
        Exception: For other unexpected errors.
    """
    stmt = (
        delete(Payment)
        .where(Payment.payment_id == payment_id)
    )
    try:
        result = await db.execute(stmt)
        await db.commit()

        was_deleted = result.rowcount is not None and result.rowcount > 0
        return was_deleted
    
    except SQLAlchemyError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    

async def update_payment(
    db: AsyncSession,
    db_payment: models.Payment,
    payment_in: schemas.PaymentUpdate
) -> models.Payment:
    """
    Updates an existing payment's mutable fields.
    Payer, payee, and group are generally not changed here.
    Returns the updated Payment ORM object. DB exceptions are re-raised.
    """

    db_payment.amount = payment_in.amount
    db_payment.payment_date = payment_in.payment_date
    db_payment.notes = payment_in.notes

    try:
        await db.commit()
        return db_payment

    except SQLAlchemyError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    

async def create_category(
    db: AsyncSession,
    category_in: TransactionCategoryCreate,
    user_id: int,
):
    db_category = TransactionCategory(
        name=category_in.name,
        user_id=user_id
    )
    db.add(db_category)

    try:
        await db.commit()
        await db.refresh(db_category)
        return db_category

    except IntegrityError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e

    except SQLAlchemyError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e

    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    

async def create_transaction(
    db: AsyncSession,
    transaction_data: TransactionCreate,
    user_id: int,
    category_id: int
) -> Transaction:
    db_transaction = Transaction(
        user_id=user_id,
        category_id=category_id,
        amount=transaction_data.amount,
        transaction_date=transaction_data.transaction_date,
        notes=transaction_data.notes
    )
    db.add(db_transaction)

    try:
        await db.commit()
        await db.refresh(db_transaction)
        return db_transaction

    except IntegrityError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    
    except SQLAlchemyError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e


async def get_category_by_name(
    db: AsyncSession,
    name: str,
    user_id: int
) -> TransactionCategory | None:
    stmt = (
        select(TransactionCategory)
        .where(
            TransactionCategory.user_id == user_id,
            TransactionCategory.name == name
        )
    )

    result = await db.execute(stmt)
    return result.scalars().first()


async def get_category_by_id(
    db: AsyncSession,
    category_id: int,
    user_id: int
) -> TransactionCategory | None:
    stmt = (
        select(TransactionCategory)
        .where(
            TransactionCategory.user_id == user_id,
            TransactionCategory.category_id == category_id
        )
    )

    result = await db.execute(stmt)
    return result.scalars().first()


async def get_category(db: AsyncSession, category_id: int, user_id: int) -> TransactionCategory | None:
    stmt = (
        select(TransactionCategory)
        .where(
            TransactionCategory.user_id == user_id,
            TransactionCategory.category_id == category_id
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user_categories(
    db: AsyncSession,
    user_id: int
) -> list[TransactionCategory]:
    stmt = (
        select(TransactionCategory)
        .where(
            TransactionCategory.user_id == user_id
        )
        .order_by(TransactionCategory.name)
    )

    result = await db.execute(stmt)
    return result.scalars().all()


async def update_category_for_user( # Renamed for clarity
    db: AsyncSession,
    db_category: TransactionCategory, # Existing ORM object
    category_update: TransactionCategoryUpdate
) -> models.TransactionCategory:
    """Updates category name. Adds to session, no commit."""
    db_category.name = category_update.name
    db.add(db_category)

    try:
        await db.flush()
        await db.refresh(db_category)
    except SQLAlchemyError:
        raise
    return db_category


async def delete_category_for_user(
    db: AsyncSession, category_id: int, user_id: int
) -> bool:
    """Deletes a category. Adds delete op to session, no commit."""
    db_category = await get_category_by_id(db, category_id, user_id)
    if not db_category:
        return False

    stmt = (
        delete(models.TransactionCategory)
        .where(
            models.TransactionCategory.id == category_id,
            models.TransactionCategory.user_id == user_id
        )
    )

    result = await db.execute(stmt)
    return result.rowcount is not None and result.rowcount > 0 


async def get_transaction(
    db: AsyncSession, transaction_id: int, user_id: int
) -> Transaction | None:
    stmt = (
        select(Transaction)
        .where(
            Transaction.transaction_id == transaction_id,
            Transaction.user_id == user_id
        )
        .options(joinedload(Transaction.category))
    )

    result = await db.execute(stmt)
    return result.scalars().first()


async def get_user_transactions(
    db: AsyncSession,
    user_id: int,
    skip: int = 0,
    limit: Optional[int] = 100
) -> list[Transaction]:
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .options(joinedload(Transaction.category))
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .offset(skip)
    )
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


async def get_group_member_ids_and_names(db: AsyncSession, group_id: int) -> list[models.User]:
    stmt = (
        select(User)
        .join(GroupMember, GroupMember.user_id == User.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(User.username)
    )

    result = await db.execute(stmt)
    user_models = result.scalars().unique().all()

    user_schemas = [schemas.User.model_validate(user) for user in user_models]
    return user_schemas


async def get_users_by_ids(db: AsyncSession, user_ids: list[int]) -> list[models.User]:
    stmt = (
        select(User)
        .where(User.user_id.in_(user_ids))
        .order_by(User.username)
    )

    result = await db.execute(stmt)
    user_models = result.scalars().unique().all()

    user_schemas = [schemas.User.model_validate(user) for user in user_models]
    return user_schemas


async def calculate_user_owed_for_bill(
    bill: Bill,
    user_id: int
) -> Decimal:
    """
    Calculates the amount a specific user owes for a single bill, based on the split method.
    This is the source of truth for what a user owes, derived from stored bill data.
    """
    total_owed_by_user = Decimal("0.00")

    if bill.split_method in [SplitMethod.equal, SplitMethod.exact]:
        # For equal and exact splits, the definitive amount is stored in bill_parts.
        user_bill_part = next((part for part in bill.bill_parts if part.user_id == user_id), None)
        if user_bill_part:
            total_owed_by_user = user_bill_part.amount_owed

    elif bill.split_method == SplitMethod.item:
        # For itemized splits, we must calculate the total from the items assigned to the user.
        if bill.items:
            for item in bill.items:
                if item.bill_item_splits:
                    user_split = next((split for split in item.bill_item_splits if split.user_id == user_id), None)
                    if user_split:
                        # Cost for this item is unit price * quantity assigned to user.
                        item_share_cost = item.unit_price * user_split.quantity
                        total_owed_by_user += item_share_cost

    # The final amount is quantized as a safeguard.
    return total_owed_by_user.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def calculate_group_net_balances(db: AsyncSession, group_id: int) -> dict[int, Decimal]:
    member_schemas = await get_group_member_ids_and_names(db=db, group_id=group_id)
    member_ids = [member.user_id for member in member_schemas]
    if not member_ids:
        return {}
    
    balances: dict[int, Decimal] = {user_id: Decimal("0.00") for user_id in member_ids}

    # Limit to fetching a large number of bills to ensure balance is correct, but not unlimited
    bills = await get_group_bills(db=db, group_id=group_id, limit=1000)
    for bill in bills:
        # First, subtract amounts for anyone who paid upfront for this bill.
        initial_payments: list[InitialPayment] = bill.initial_payments
        for initial_payment in initial_payments:
            if initial_payment.user_id in balances:
                balances[initial_payment.user_id] -= initial_payment.amount_paid

        # Determine the unique set of users who are assigned a portion of this bill.
        bill_participant_ids = {part.user_id for part in bill.bill_parts}
        for item in bill.items:
            for split in item.bill_item_splits:
                bill_participant_ids.add(split.user_id)

        # Now, only iterate over users who were actually part of this bill's split.
        for user_id in bill_participant_ids:
            # Ensure we only process users who are still current members of the group.
            if user_id in balances:
                amount_owed = await calculate_user_owed_for_bill(
                    bill=bill,
                    user_id=user_id
                )
                if amount_owed > Decimal("0.00"):
                    balances[user_id] += amount_owed
    
    # Limit to fetching a large number of payments to ensure balance is correct
    payments = await get_group_payments(db=db, group_id=group_id, limit=1000)
    for payment in payments:
        if payment.payer_id in balances:
            balances[payment.payer_id] -= payment.amount
        if payment.payee_id in balances:
            balances[payment.payee_id] += payment.amount

    return balances


# Temp class for payer_id and payee_id storing
class _SuggestedPayment:
    def __init__(self, payer_id: int, payee_id: int, amount: Decimal):
        self.payer_id = payer_id
        self.payee_id = payee_id
        self.amount = amount


# Calculate a list of suggested payments to settle all debts within a group
async def calculate_suggested_settlements(
    net_balances: dict[int, Decimal]
) -> list[_SuggestedPayment]:
    debtors = {user_id: amount for user_id, amount in net_balances.items() if amount > Decimal("0")}
    creditors = {user_id: -amount for user_id, amount in net_balances.items() if amount < Decimal("0")}

    suggested_payments: list[_SuggestedPayment] = []

    # Using lists for easier modification
    debtor_list = [(uid, amt) for uid, amt in debtors.items()]
    creditor_list = [(uid, amt) for uid, amt in creditors.items()]


    debtor_idx = 0
    creditor_idx = 0

    while debtor_idx < len(debtor_list) and creditor_idx < len(creditor_list):
        payer_id, amount_owed_by_payer = debtor_list[debtor_idx]
        payee_id, amount_due_to_payee = creditor_list[creditor_idx]

        # Determine the amount to transfer in this step
        transfer_amount = min(amount_owed_by_payer, amount_due_to_payee)

        if transfer_amount > Decimal("0.005"): # Avoid tiny (e.g. 0.001) transfers due to precision
            suggested_payments.append(
                _SuggestedPayment(
                    payer_id=payer_id,
                    payee_id=payee_id,
                    amount=transfer_amount.quantize(Decimal("0.01"))
                )
            )

            # Update remaining balances
            new_amount_owed_by_payer = amount_owed_by_payer - transfer_amount
            new_amount_due_to_payee = amount_due_to_payee - transfer_amount

            debtor_list[debtor_idx] = (payer_id, new_amount_owed_by_payer)
            creditor_list[creditor_idx] = (payee_id, new_amount_due_to_payee)

        # Move to the next debtor if their debt is settled
        if new_amount_owed_by_payer <= Decimal("0.005"):
            debtor_idx += 1
        
        # Move to the next creditor if their credit is fulfilled
        if new_amount_due_to_payee <= Decimal("0.005"):
            creditor_idx += 1

    return suggested_payments


async def get_payments_between_users_in_group(
    db: AsyncSession,
    group_id: int,
    user_a_id: int,
    user_b_id: int,
):
    stmt = (
        select(Payment)
        .where(
            Payment.group_id == group_id,
            or_(
                (Payment.payer_id == user_a_id) & (Payment.payee_id == user_b_id),
                (Payment.payer_id == user_b_id) & (Payment.payee_id == user_a_id)
            )
        )
        .options(
            joinedload(Payment.payer),
            joinedload(Payment.payee)
        )
    )

    result = await db.execute(stmt)
    return result.scalars().all()


async def get_user_share_for_bill(
    db: AsyncSession,
    bill: Bill,
    target_user_id: int,
):
    split_method = bill.split_method
    items: list[BillItem] = bill.items
    bill_parts: list[BillPart] = bill.bill_parts

    user_monetary_share = Decimal("0.0")

    if split_method == SplitMethod.equal or split_method == SplitMethod.exact:
        if bill_parts:
            user_bill_part = next((part for part in bill_parts if part.user_id == target_user_id), None)
            if user_bill_part:
                user_monetary_share = user_bill_part.amount_owed

    elif split_method == SplitMethod.item:
        if items:
            for item in items:
                bill_item_splits: list[BillItemSplit] = item.bill_item_splits
                if bill_item_splits:
                    user_item_split = next((split for split in bill_item_splits if split.user_id == target_user_id), None)
                    if user_item_split:
                        item_share_cost = item.unit_price * user_item_split.quantity
                        user_monetary_share += item_share_cost
    
    return user_monetary_share.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            
    

async def calculate_balance_between_two_users(
    db: AsyncSession,
    group_id: int,
    user1_id: int, # The "current user" perspective
    user2_id: int, # The "other user"
) -> Decimal:
    if user1_id == user2_id:
        return Decimal("0")

    u1_owes_u2 = Decimal("0")

    # Check direct payments
    direct_payments = await get_payments_between_users_in_group(
        db=db, group_id=group_id, user_a_id=user1_id, user_b_id=user2_id
    )
    for payment in direct_payments:
        if payment.payer_id == user1_id: # User1 paid User2
            u1_owes_u2 -= payment.amount
        elif payment.payer_id == user2_id: # User2 paid User1
            u1_owes_u2 += payment.amount

    # Check all bills, find bill involving both users
    group_bills = await get_group_bills(db=db, group_id=group_id)
    for bill in group_bills:
        u1_share = await get_user_share_for_bill(db=db, bill=bill, target_user_id=user1_id)
        u2_share = await get_user_share_for_bill(db=db, bill=bill, target_user_id=user2_id)

        # Only consider this bill if both users actually have a share in it
        if u1_share > 0 or u2_share > 0:
            initial_payments: list[InitialPayment] = bill.initial_payments
            u1_paid_initially = sum(ip.amount_paid for ip in initial_payments if ip.user_id == user1_id)
            u2_paid_initially = sum(ip.amount_paid for ip in initial_payments if ip.user_id == user2_id)

            # If User2 paid more than their own share, that surplus could cover User1's deficit.
            u2_surplus_on_bill = u2_paid_initially - u2_share
            if u2_surplus_on_bill > 0 and u1_share > 0:
                amount_u2_covered_for_u1 = min(u2_surplus_on_bill, u1_share)
                u1_owes_u2 += amount_u2_covered_for_u1 # User1 owes User2 for this amount

            # If User1 paid more than their own share, that surplus could cover User2's deficit.
            u1_surplus_on_bill = u1_paid_initially - u1_share
            if u1_surplus_on_bill > 0 and u2_share > 0:
                amount_u1_covered_for_u2 = min(u1_surplus_on_bill, u2_share)
                u1_owes_u2 -= amount_u1_covered_for_u2 # User1 is owed by User2 (so it reduces u1_owes_u2)
                
    return u1_owes_u2.quantize(Decimal("1"))


async def update_user(
    db: AsyncSession,
    db_user: models.User,
    user_in: schemas.UserUpdate,
) -> models.User:
    """
    Updates a user's profile information (username, full_name).
    This function adds the updated user object to the session but does NOT commit.
    The calling function is responsible for the commit.
    """
    update_data = user_in.model_dump(exclude_unset=True)

    if "username" in update_data:
        db_user.username = update_data["username"]

    if "full_name" in update_data:
        db_user.full_name = update_data["full_name"]

    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    return db_user
    

async def create_notification(
    db: AsyncSession,
    recipient_user_id: int,
    message: str,
    notification_type: Optional[NotificationType] = None,
    related_group_id: Optional[int] = None,
    related_bill_id: Optional[int] = None,
    related_payment_id: Optional[int] = None,
    related_user_id: Optional[int] = None, # User who triggered the notification
) -> Notification:
    """
    Creates a new notification in the database.
    This function will typically be called *within* another transaction
    (e.g., after creating a bill, before the final commit of that operation).
    It does not commit independently here.
    """
    db_notification = models.Notification(
        recipient_user_id=recipient_user_id,
        message=message,
        notification_type=notification_type,
        related_group_id=related_group_id,
        related_bill_id=related_bill_id,
        related_payment_id=related_payment_id,
        related_user_id=related_user_id,
    )

    db.add(db_notification)
    return db_notification


async def get_notifications_for_user(
    db: AsyncSession,
    user_id: int,
    skip: int = 0,
    limit: int = 20, # Default limit for listing
    unread_only: bool = False
) -> list[Notification]:
    """
    Retrieves notifications for a specific user, with pagination and unread filter.
    """
    stmt = (
        select(models.Notification)
        .where(models.Notification.recipient_user_id == user_id)
        .options(
            joinedload(models.Notification.recipient)
        )
    )

    if unread_only:
        stmt = stmt.where(models.Notification.is_read == False)

    stmt = stmt.order_by(models.Notification.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_notification_by_id_for_user(
    db: AsyncSession, notification_id: int, user_id: int
) -> Optional[models.Notification]:
    """
    Retrieves a specific notification by its ID, ensuring it belongs to the user.
    """
    stmt = (
        select(models.Notification)
        .where(
            models.Notification.id == notification_id,
            models.Notification.recipient_user_id == user_id
        )
        .options(
            joinedload(models.Notification.recipient)
        )
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def mark_notification_as_read(
    db: AsyncSession, db_notification: models.Notification
) -> models.Notification:
    """
    Marks a given notification object as read.
    Assumes db_notification is a valid notification for the current user.
    """
    if not db_notification.is_read:
        db_notification.is_read = True

        try:
            await db.commit()
            await db.refresh(db_notification)
        except SQLAlchemyError as e:
            await db.rollback()
            raise e
    return db_notification


async def mark_all_notifications_as_read(db: AsyncSession, user_id: int) -> int:
    """Marks all unread notifications for a user as read. Returns count of updated notifications."""
    stmt = (
        update(models.Notification)
        .where(
            models.Notification.recipient_user_id == user_id,
            models.Notification.is_read == False
        )
        .values(is_read=True)
    )

    try:
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
    
    except SQLAlchemyError as e:
        await db.rollback()
        raise e
    

async def get_unread_notification_count(db: AsyncSession, user_id: int) -> int:
    """Gets the count of unread notifications for a user."""
    stmt = (
        select(func.count(models.Notification.id))
        .where(
            models.Notification.recipient_user_id == user_id,
            models.Notification.is_read == False
        )
    )

    result = await db.execute(stmt)
    count = result.scalar_one_or_none()
    return count if count is not None else 0


async def get_recent_member_joins_for_activity(
    db: AsyncSession, group_id: int, limit: int = 10
) -> list[models.GroupMember]:
    """
    Retrieves recent GroupMember entries (joins) for the activity feed,
    with user details eager loaded.
    """
    stmt = (
        select(models.GroupMember)
        .where(models.GroupMember.group_id == group_id)
        .options(joinedload(models.GroupMember.user))
        .order_by(models.GroupMember.joined_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().unique().all()


async def get_recent_member_leaves_for_activity(
    db: AsyncSession, group_id: int, limit: int = 10
) -> list[models.GroupMember]:
    """
    Retrieves recent GroupMember entries where a user left (left_at is set)
    for the activity feed, with user details eager loaded.
    """
    stmt = (
        select(models.GroupMember)
        .where(
            models.GroupMember.group_id == group_id,
            models.GroupMember.left_at != None
        )
        .options(joinedload(models.GroupMember.user))
        .order_by(models.GroupMember.left_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().unique().all()


async def get_recent_bills_for_activity_feed(
    db: AsyncSession, group_id: int, limit: int = 10
) -> list[models.Bill]:
    """
    Retrieves recent Bills created in a group for the activity feed.
    Eager loads the bill creator's user details.
    """
    stmt = (
        select(models.Bill)
        .where(models.Bill.group_id == group_id)
        .options(
            selectinload(Bill.initial_payments).joinedload(models.InitialPayment.user),
            selectinload(Bill.bill_parts).selectinload(models.BillPart.user),
            selectinload(Bill.items)
                .selectinload(models.BillItem.bill_item_splits)
                    .joinedload(models.BillItemSplit.user),
            joinedload(Bill.bill_creator),
            selectinload(Bill.category)
        )
        .order_by(models.Bill.created_at.desc())
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    return result.scalars().unique().all()


async def get_recent_payments_for_activity_feed(
    db: AsyncSession, group_id: int, limit: int = 10
) -> list[models.Payment]:
    """
    Retrieves recent Payments made in a group for the activity feed.
    Eager loads payer and payee user details.
    Uses `created_at` for ordering; if `payment_date` is more relevant for activity, use that.
    """
    stmt = (
        select(models.Payment)
        .where(models.Payment.group_id == group_id)
        .options(
            joinedload(models.Payment.payer),
            joinedload(models.Payment.payee)
        )
        .order_by(models.Payment.created_at.desc())
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    return result.scalars().unique().all()


async def create_audit_log_entry(
    db: AsyncSession,
    action_type: AuditActionType,
    actor_user_id: Optional[int] = None,
    group_id: Optional[int] = None,
    target_bill_id: Optional[int] = None,
    target_payment_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    summary_message: Optional[str] = None,
) -> models.AuditLogEntry:
    db_log_entry = models.AuditLogEntry(
        actor_user_id=actor_user_id,
        action_type=action_type,
        group_id=group_id,
        target_bill_id=target_bill_id,
        target_payment_id=target_payment_id,
        target_user_id=target_user_id,
        summary_message=summary_message
    )

    db.add(db_log_entry)
    try:
        await db.commit()
        await db.refresh(db_log_entry)
        return db_log_entry

    except IntegrityError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    
    except SQLAlchemyError as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        raise e
    

async def get_group_audit_log_entries(
    db: AsyncSession, 
    group_id: int, 
    skip: int = 0, 
    limit: int = 20
) -> list[models.AuditLogEntry]:
    """
    Retrieves paginated audit log entries for a specific group, ordered by most recent.
    """
    stmt = (
        select(models.AuditLogEntry)
        .where(models.AuditLogEntry.group_id == group_id)
        .options(joinedload(models.AuditLogEntry.actor))
        .order_by(models.AuditLogEntry.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_transaction(
    db: AsyncSession,
    db_transaction: models.Transaction,
    transaction_update: schemas.TransactionUpdate,
    category_id: Optional[int] = None,
) -> models.Transaction:
    """
    Updates an existing transaction with new data.
    Does not commit - transaction handling is done in the router.
    """
    update_data = transaction_update.model_dump(exclude_unset=True)
    
    if category_id is not None:
        update_data["category_id"] = category_id

    for field, value in update_data.items():
        setattr(db_transaction, field, value)

    db.add(db_transaction)
    try:
        await db.flush()
        await db.refresh(db_transaction)
        return db_transaction
    except IntegrityError as e:
        raise e
    except Exception as e:
        raise e


async def delete_transaction(
    db: AsyncSession,
    transaction_id: int,
    user_id: int
) -> bool:
    """
    Deletes a transaction. Returns True if successful, False if transaction not found.
    Does not commit - transaction handling is done in the router.
    """
    stmt = (
        delete(models.Transaction)
        .where(
            models.Transaction.transaction_id == transaction_id,
            models.Transaction.user_id == user_id
        )
    )

    try:
        result = await db.execute(stmt)
        return result.rowcount > 0  # True if a row was deleted
    except IntegrityError as e:
        raise e
    except Exception as e:
        raise e


async def update_group(
    db: AsyncSession, group_id: int, group_update: schemas.GroupUpdate
) -> models.Group | None:
    db_group = await get_group(db, group_id)
    if not db_group:
        return None
    
    update_data = group_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_group, key, value)
        
    await db.commit()
    await db.refresh(db_group)
    return db_group


async def calculate_all_balances_for_user_in_group(
    db: AsyncSession,
    group_id: int,
    current_user_id: int
) -> list[tuple[models.User, Decimal]]:
    
    all_members_stmt = (
        select(models.User)
        .join(models.GroupMember)
        .where(
            models.GroupMember.group_id == group_id,
            models.User.user_id != current_user_id
        )
    )
    result = await db.execute(all_members_stmt)
    other_members = result.scalars().all()

    balances = []
    for member in other_members:
        balance = await calculate_balance_between_two_users(
            db=db,
            group_id=group_id,
            user1_id=current_user_id,
            user2_id=member.user_id
        )
        balances.append((member, balance))
            
    return balances

# --- Friendship CRUD Functions ---

async def create_friendship(db: AsyncSession, friendship_in: FriendshipCreate, requester_id: int) -> Friendship:
    if requester_id == friendship_in.addressee_id:
        raise ValueError("Cannot create a friendship with oneself.")
    
    # Check for existing friendship/request
    existing = await get_friendship_by_users(db, user_id_1=requester_id, user_id_2=friendship_in.addressee_id)
    if existing:
        if existing.status == FriendshipStatus.accepted:
            raise IntegrityError("Users are already friends.", params=None, orig=None)
        elif existing.status == FriendshipStatus.pending:
            raise IntegrityError("A friend request is already pending.", params=None, orig=None)

    db_friendship = Friendship(
        requester_id=requester_id,
        addressee_id=friendship_in.addressee_id,
        status=FriendshipStatus.pending
    )
    db.add(db_friendship)
    return db_friendship


async def get_friendship_by_users(db: AsyncSession, user_id_1: int, user_id_2: int) -> Friendship | None:
    """Gets a friendship record between two users, regardless of who is requester/addressee."""
    stmt = (
        select(Friendship)
        .where(
            or_(
                (Friendship.requester_id == user_id_1) & (Friendship.addressee_id == user_id_2),
                (Friendship.requester_id == user_id_2) & (Friendship.addressee_id == user_id_1)
            )
        )
        .options(
            joinedload(Friendship.requester),
            joinedload(Friendship.addressee)
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def can_send_friend_request(db: AsyncSession, user_id_1: int, user_id_2: int) -> bool:
    """Checks if a friend request can be sent between two users."""
    if user_id_1 == user_id_2:
        return False
        
    existing_friendship = await get_friendship_by_users(db, user_id_1, user_id_2)
    if existing_friendship:
        return False
    
    return True


async def get_friendships_for_user(db: AsyncSession, user_id: int) -> list[Friendship]:
    """Gets all friendships (accepted) for a given user."""
    stmt = select(Friendship).where(
        (Friendship.requester_id == user_id) | (Friendship.addressee_id == user_id),
        Friendship.status == FriendshipStatus.accepted
    ).options(
        joinedload(Friendship.requester),
        joinedload(Friendship.addressee)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_received_pending_friend_requests(db: AsyncSession, user_id: int) -> list[Friendship]:
    """Gets all pending friend requests for a given user (where they are the addressee)."""
    stmt = select(Friendship).where(
        (Friendship.addressee_id == user_id),
        Friendship.status == FriendshipStatus.pending
    ).options(
        joinedload(Friendship.requester),
        joinedload(Friendship.addressee)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_sent_pending_friend_requests(db: AsyncSession, user_id: int) -> list[Friendship]:
    """Gets all pending friend requests sent by a given user (where they are the requester)."""
    stmt = select(Friendship).where(
        (Friendship.requester_id == user_id),
        Friendship.status == FriendshipStatus.pending
    ).options(
        joinedload(Friendship.requester),
        joinedload(Friendship.addressee)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_friendship(db: AsyncSession, db_friendship: Friendship, friendship_up: FriendshipUpdate) -> Friendship:
    """Updates the status of a friendship to ACCEPTED. Does not commit."""
    # This function now only handles accepting friendships.
    # Declining is handled by delete_friendship.
    if friendship_up.status == FriendshipStatus.accepted:
        db_friendship.status = FriendshipStatus.accepted
        db.add(db_friendship) # Add to session to track changes
        await db.flush()
    return db_friendship


async def delete_friendship(db: AsyncSession, db_friendship: Friendship):
    """Deletes a friendship record. Does not commit."""
    await db.delete(db_friendship)
    await db.flush()


# --- Group Invitation CRUD Functions ---

async def create_group_invitation(db: AsyncSession, inv_in: GroupInvitationCreate, group_id: int, inviter_id: int) -> GroupInvitation:
    """Creates a new group invitation. Does not commit."""
    if inviter_id == inv_in.invitee_id:
        raise ValueError("Cannot invite oneself to a group.")
        
    db_invitation = GroupInvitation(
        group_id=group_id,
        inviter_id=inviter_id,
        invitee_id=inv_in.invitee_id,
        status=GroupInvitationStatus.pending
    )
    db.add(db_invitation)
    await db.flush()
    await db.refresh(db_invitation)
    return db_invitation


async def get_group_invitation_by_id(db: AsyncSession, invitation_id: int) -> GroupInvitation | None:
    """Gets a specific group invitation by its ID, with all relationships eager-loaded."""
    stmt = (
        select(GroupInvitation)
        .where(GroupInvitation.invitation_id == invitation_id)
        .options(
            joinedload(GroupInvitation.inviter),
            joinedload(GroupInvitation.invitee),
            joinedload(GroupInvitation.group)
                .selectinload(models.Group.members)
                .joinedload(models.GroupMember.user),
            joinedload(GroupInvitation.group)
                .selectinload(models.Group.bill_categories)
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_pending_invitations_for_user(db: AsyncSession, user_id: int) -> list[GroupInvitation]:
    """Gets all pending group invitations for a specific user."""
    stmt = select(GroupInvitation).where(
        GroupInvitation.invitee_id == user_id,
        GroupInvitation.status == GroupInvitationStatus.pending
    ).options(
        joinedload(GroupInvitation.group).selectinload(models.Group.members).joinedload(models.GroupMember.user),
        joinedload(GroupInvitation.group).selectinload(models.Group.bill_categories),
        joinedload(GroupInvitation.inviter)
    )
    result = await db.execute(stmt)
    return result.scalars().unique().all()

    
async def update_group_invitation(db: AsyncSession, db_invitation: GroupInvitation, inv_up: GroupInvitationUpdate) -> GroupInvitation:
    """Updates the status of a group invitation. Does not commit."""
    db_invitation.status = inv_up.status
    db.add(db_invitation) # Add to session to track changes
    
    # If the invitation is accepted, add the user to the group
    if inv_up.status == GroupInvitationStatus.accepted:
        # Check if user is already a member to avoid errors
        is_member = await is_member_of_group(db, user_id=db_invitation.invitee_id, group_id=db_invitation.group_id)
        if not is_member:
            await add_user_to_group(
                db=db,
                group_id=db_invitation.group_id,
                user_id=db_invitation.invitee_id,
                role=GroupRole.member # Default role for accepted invites
            )
            
    await db.flush()
    await db.refresh(db_invitation)
    return db_invitation


async def get_pending_invitations_for_group(db: AsyncSession, group_id: int) -> list[GroupInvitation]:
    """Gets all pending invitations for a specific group, with inviter and invitee info."""
    stmt = select(GroupInvitation).where(
        GroupInvitation.group_id == group_id,
        GroupInvitation.status == GroupInvitationStatus.pending
    ).options(
        joinedload(GroupInvitation.inviter),
        joinedload(GroupInvitation.invitee),
        joinedload(GroupInvitation.group)
            .selectinload(models.Group.members)
            .joinedload(models.GroupMember.user),
        joinedload(GroupInvitation.group)
            .selectinload(models.Group.bill_categories),
    ).order_by(GroupInvitation.created_at.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_group_payments(
    db: AsyncSession,
    group_id: int,
    skip: int = 0,
    limit: Optional[int] = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter_type: str = "all",
    member_a_id: Optional[int] = None,
    member_b_id: Optional[int] = None
) -> list[Payment]:
    stmt = (
        select(Payment)
        .where(Payment.group_id == group_id)
        .options(
            joinedload(Payment.payer),
            joinedload(Payment.payee)
        )
    )

    # Filtering logic
    if filter_type != "all" and member_a_id is not None:
        if filter_type == "involving":
            stmt = stmt.where(or_(Payment.payer_id == member_a_id, Payment.payee_id == member_a_id))
        elif filter_type == "from_member":
            stmt = stmt.where(Payment.payer_id == member_a_id)
        elif filter_type == "to_member":
            stmt = stmt.where(Payment.payee_id == member_a_id)
        elif filter_type == "between" and member_b_id is not None:
            stmt = stmt.where(
                or_(
                    (Payment.payer_id == member_a_id) & (Payment.payee_id == member_b_id),
                    (Payment.payer_id == member_b_id) & (Payment.payee_id == member_a_id)
                )
            )

    # Sorting logic
    sort_column = getattr(Payment, sort_by, Payment.created_at)
    if sort_order == "desc":
        stmt = stmt.order_by(sort_column.desc())
    else:
        stmt = stmt.order_by(sort_column.asc())

    # Default secondary sort for stable ordering
    if sort_by != 'created_at':
        stmt = stmt.order_by(Payment.created_at.desc())


    stmt = stmt.offset(skip)

    if limit is not None and limit > 0: # Also check limit > 0 to avoid LIMIT 0
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


async def get_invitation_by_group_and_invitee(db: AsyncSession, group_id: int, invitee_id: int) -> GroupInvitation | None:
    """Gets an invitation for a specific user in a specific group, regardless of status."""
    stmt = select(GroupInvitation).where(
        GroupInvitation.group_id == group_id,
        GroupInvitation.invitee_id == invitee_id
    ).options(
        joinedload(GroupInvitation.group)
            .selectinload(models.Group.members)
            .joinedload(models.GroupMember.user),
        joinedload(GroupInvitation.group)
            .selectinload(models.Group.bill_categories),
        joinedload(GroupInvitation.inviter),
        joinedload(GroupInvitation.invitee),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_user_profile_image(db: AsyncSession, user_id: int, image_url: str) -> User:
    """
    Updates only the profile_image_url for a given user.
    """
    db_user = await get_user_by_user_id(db, user_id=user_id)
    if not db_user:
        raise ValueError("User not found") # Or a more specific exception
    
    db_user.profile_image_url = image_url
    db.add(db_user)
    return db_user


async def get_user_by_google_id(db: AsyncSession, google_id: str) -> Optional[User]:
    result = await db.execute(select(User).filter(User.google_id == google_id))
    return result.scalars().first()


async def get_group_member(db: AsyncSession, group_id: int, user_id: int) -> models.GroupMember | None:
    result = await db.execute(select(models.GroupMember).filter_by(group_id=group_id, user_id=user_id))
    return result.scalars().first()


async def update_member_role(db: AsyncSession, group_id: int, user_id: int, new_role: models.GroupRole) -> models.GroupMember | None:
    """
    Updates the role of a member in a group.
    """
    member = await get_group_member(db, group_id=group_id, user_id=user_id)
    if member:
        member.role = new_role
        await db.flush()
        await db.refresh(member)
    return member


async def swap_owner_with_admin(db: AsyncSession, group_id: int, current_owner_id: int, new_owner_id: int) -> models.GroupMember | None:
    """
    Swaps the roles of the current owner and an admin.
    Returns the membership of the new owner.
    """
    current_owner_membership = await get_group_member(db, group_id=group_id, user_id=current_owner_id)
    new_owner_membership = await get_group_member(db, group_id=group_id, user_id=new_owner_id)

    if not all([current_owner_membership, new_owner_membership]):
        return None # Or raise an error
    
    # Swap roles
    current_owner_membership.role = models.GroupRole.admin
    new_owner_membership.role = models.GroupRole.owner
    
    await db.flush()
    await db.refresh(new_owner_membership)
    await db.refresh(current_owner_membership)

    return new_owner_membership


async def get_spending_by_category_for_group(
    db: AsyncSession, group_id: int, year: int, month: int, include_uncategorized: bool = True
) -> list[tuple[str, Decimal]]:
    """
    Calculates the total spending per bill category for a given group and month.
    Optionally includes the total for uncategorized bills (category_id is NULL) as 'Uncategorized'.
    """
    # Spending by category
    stmt = (
        select(
            models.BillCategory.name,
            func.sum(models.Bill.total_amount).label("total_amount")
        )
        .join(models.Bill, models.Bill.category_id == models.BillCategory.category_id)
        .where(
            models.Bill.group_id == group_id,
            extract('year', models.Bill.created_at) == year,
            extract('month', models.Bill.created_at) == month
        )
        .group_by(models.BillCategory.name)
        .order_by(desc("total_amount"))
    )
    result = await db.execute(stmt)
    category_results = result.all()

    if include_uncategorized:
        # Spending for uncategorized bills
        uncategorized_stmt = (
            select(
                func.sum(models.Bill.total_amount).label("total_amount")
            )
            .where(
                models.Bill.group_id == group_id,
                models.Bill.category_id == None,
                extract('year', models.Bill.created_at) == year,
                extract('month', models.Bill.created_at) == month
            )
        )
        uncategorized_result = await db.execute(uncategorized_stmt)
        uncategorized_total = uncategorized_result.scalar()
        if uncategorized_total:
            category_results.append(("Uncategorized", uncategorized_total))

    return category_results