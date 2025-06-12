from pydantic import BaseModel, EmailStr, Field, computed_field, model_validator, constr

from backend.models import GroupRole, SplitMethod, NotificationType, AuditActionType, FriendshipStatus, GroupInvitationStatus
from typing import Optional, Literal, Union, List, Dict
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import enum

class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None
    profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="New username")
    full_name: Optional[str] = Field(None, max_length=100, description="New full name")


class User(UserBase):
    user_id: int
    is_active: bool

    class Config:
        from_attributes = True


# JWT
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    subject: str | None = None


# GroupMember
class GroupMember(BaseModel):
    group_id: int
    role: GroupRole
    user: Optional[User] = None
    joined_at: datetime

    class Config:
        from_attributes = True


class GroupMemberCreate(BaseModel):
    user_id: int
    role: GroupRole = GroupRole.member


# Group
class GroupBase(BaseModel):
    group_name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


class GroupCreate(GroupBase):
    pass


class GroupUpdate(GroupBase):
    group_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


class Group(GroupBase):
    group_id: int
    members: list[GroupMember]
    bill_categories: list["BillCategory"] = []

    class Config:
        from_attributes = True


# Bill
class BillBase(BaseModel):
    """Base schema for Bill data."""
    title: str
    description: str | None
    total_amount: Decimal = Field(..., gt=Decimal("0.0")) # Add validation
    receipt_image_url: Optional[str] = None
    split_method: SplitMethod


class ExistingBillCategory(BaseModel):
    type: Literal["existing"] = "existing"
    category_id: int


class NewBillCategory(BaseModel):
    type: Literal["new"] = "new"
    name: str = Field(..., min_length=1, max_length=100)


class InitialPaymentCreate(BaseModel):
    """Schema for creating an Initial Payment record."""
    user_id: int
    amount_paid: Decimal = Field(..., gt=Decimal("0.0")) # Add validation


class InitialPayment(BaseModel):
    """Schema for representing an Initial Payment in responses."""
    amount_paid: Decimal
    user: Optional[User] = None # Optional nested user details

    class Config:
        from_attributes = True


# Bill Item
class BillItemSplitCreate(BaseModel):
    """Schema for creating a split for a specific Bill Item."""
    user_id: int
    quantity: int = Field(..., gt=0)


class BillItemSplit(BaseModel):
    """Schema for representing a Bill Item split in responses."""
    quantity: int
    user: Optional[User] = None # Optional nested user details

    class Config:
        from_attributes = True


class BillItemCreate(BaseModel):
    """Schema for creating a Bill Item."""
    name: str
    unit_price: Decimal = Field(..., gt=Decimal("0.0"))
    quantity: int = Field(..., gt=0)
    # Splits are required if the Bill's split_method is 'item'
    # Making it optional allows flexibility, validation should enforce based on parent Bill's method
    splits: Optional[list[BillItemSplitCreate]] = None

    # Optional: Add validator to check sum(splits.quantity) == self.quantity
    # This validation might be better placed in the BillCreate schema or endpoint
    # as it depends on the overall split_method.


class BillItem(BaseModel):
    """Schema for representing a Bill Item in responses."""
    item_id: int
    name: str
    unit_price: Decimal
    quantity: int
    # Splits will be populated if they exist and are loaded
    bill_item_splits: list[BillItemSplit] = []

    class Config:
        from_attributes = True


# Bill Part
class BillPartCreate(BaseModel):
    """Schema for creating a Bill Part (exact amount split)."""
    user_id: int
    amount_owed: Decimal = Field(..., ge=Decimal("0.0"))


class BillPart(BaseModel):
    """Schema representing a Bill Part (exact amount split) from the DB."""
    amount_owed: Decimal
    user: Optional[User] = None

    @property
    def user_id(self) -> int:
        """Get user_id from the user relationship."""
        if not self.user:
            raise ValueError("User relationship not loaded")
        return self.user.user_id

    class Config:
        from_attributes = True


# Bill
# --- BillCreate Schema ---
def validate_splits(
    split_method: SplitMethod,
    initial_payments: list[InitialPaymentCreate],
    items: list[BillItemCreate],
    total_amount: Decimal,
    bill_parts: Optional[list[BillPartCreate]] = None,
):
    total_initial_payments = sum(payment.amount_paid for payment in initial_payments) if initial_payments else Decimal("0")
    if total_initial_payments > total_amount:
        raise ValueError(
            f"The sum of initial payments ({total_initial_payments}) cannot exceed the total amount ({total_amount})."
        )

    if not items: # Items list is empty or not provided
        if split_method == SplitMethod.item:
            raise ValueError("An itemized bill (split_method='item') must include at least one item.")
    else:
        # Items provided, check sum of items
        total_price = sum(item_data.unit_price * item_data.quantity for item_data in items)
        if abs(total_price - total_amount) > Decimal("0.01"):
            raise ValueError(f"Total price ({total_price}) does not match the total amount ({total_amount}).")

    # Exact amount split
    if split_method == SplitMethod.exact:
        if not bill_parts:
            raise ValueError("Bill parts (exact amounts) are required for 'exact' split method.")
        
        total_split_amount = sum(part.amount_owed for part in bill_parts)
        if not abs(total_split_amount - total_amount) < Decimal("0.01"):
            raise ValueError(f"Split amounts must sum to the total bill amount. Current sum: {total_split_amount}, Bill total: {total_amount}")

    # Item split
    elif split_method == SplitMethod.item:
        if bill_parts:
            raise ValueError("Bill-level exact amount splits (bill_parts) are not allowed for 'item' split method.")
        
        for idx, item_data in enumerate(items):
            if not item_data.splits:
                raise ValueError(
                    f"No splits provided for item '{item_data.name}' (index {idx}) "
                    f"when split_method is 'item'."
                )
            
            total_split_quantity = sum(split.quantity for split in item_data.splits)
            if total_split_quantity != item_data.quantity:
                raise ValueError(
                    f"Split quantities ({total_split_quantity}) for item '{item_data.name}' (index {idx}) "
                    f"do not sum to item quantity ({item_data.quantity})."
                )

    # Equal split
    elif split_method == SplitMethod.equal:
        if bill_parts:
            raise ValueError("Bill-level exact amount splits (bill_parts) are not allowed for 'equal' split method.")
        
        # For 'equal' split, individual items should not have their own splits.
        for idx, item_data in enumerate(items):
            if item_data.splits: # True if item_data.splits is not None and not an empty list
                raise ValueError(
                    f"Item-level splits for item '{item_data.name}' (index {idx}) "
                    "are not allowed when split_method is 'equal'."
                )


class BillCreate(BillBase):
    """Schema for creating a new Bill."""
    category_input: Optional[Union[ExistingBillCategory, NewBillCategory]] = Field(None, discriminator='type')
    initial_payments: list[InitialPaymentCreate] = Field(default_factory=list)
    items: list[BillItemCreate] = Field(default_factory=list)
    # Only include bill_parts if split_method is 'exact'
    bill_parts: Optional[list[BillPartCreate]] = None

    # --- Validator for Input Consistency ---
    @model_validator(mode='after')
    def check_splits_based_on_method(self) -> 'BillCreate':
        validate_splits(
            split_method=self.split_method,
            initial_payments=self.initial_payments,
            items=self.items,
            bill_parts=self.bill_parts,
            total_amount=self.total_amount
        )
        return self

    
class Bill(BillBase):
    """Schema for representing a full Bill in responses."""
    bill_id: int
    group_id: int
    created_by: Optional[int]
    created_at: datetime
    receipt_image_url: Optional[str] = None
    category_id: Optional[int] = None
    category: Optional["BillCategory"] = None

    initial_payments: list[InitialPayment] = []
    items: list[BillItem] = [] # Includes nested splits if loaded
    bill_parts: list[BillPart] = [] # Now contains exact amounts
    bill_creator: Optional[User] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: str(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        }


class BillUpdate(BaseModel): # Updated to not inherit from BillBase
    """Schema for updating an existing Bill. Expects the full new state."""
    title: str
    description: str | None
    total_amount: Decimal = Field(..., gt=Decimal("0.0"))
    receipt_image_url: Optional[str] = None
    split_method: SplitMethod
    category_input: Optional[Union[ExistingBillCategory, NewBillCategory]] = Field(None, discriminator='type')
    initial_payments: list[InitialPaymentCreate] = Field(default_factory=list)
    items: list[BillItemCreate] = Field(default_factory=list)
    bill_parts: Optional[list[BillPartCreate]] = None

    @model_validator(mode='after')
    def check_splits_based_on_method(self) -> 'BillUpdate':
        validate_splits(
            split_method=self.split_method,
            initial_payments=self.initial_payments,
            items=self.items,
            bill_parts=self.bill_parts,
            total_amount=self.total_amount
        )
        return self

    class Config:
        from_attributes = True # If you intend to create this from a model instance sometimes


# Bill Category
class BillCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

    class Config:
        from_attributes = True

class BillCategoryCreate(BillCategoryBase):
    group_id: Optional[int] = None # Can be null for default categories

class BillCategory(BillCategoryBase):
    category_id: int
    group_id: Optional[int] = None


# Payment
class PaymentBase(BaseModel):
    payee_id: int
    amount: Decimal = Field(..., gt=Decimal("0.0"))
    bill_id: Optional[int] = Field(None, description="Optional ID of the bill this payment settles")
    notes: Optional[str] = Field(None, description="Optional notes for the payment")
    payment_date: Optional[date] = Field(None, description="Date of the payment (defaults to today if not provided)")


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0.0"))
    payment_date: date
    notes: Optional[str] = Field(None, max_length=255) # Notes can be explicitly set to null or a string
    bill_id: Optional[int] = Field(None) # bill_id can be set to null or an int

    class Config:
        from_attributes = True


class Payment(BaseModel):
    """Schema for representing a Payment in responses."""
    payment_id: int
    group_id: int
    bill_id: Optional[int]
    amount: Decimal
    notes: Optional[str]
    created_at: datetime

    # Optional: Include nested user details for payer/payee
    payer: Optional[User] = None
    payee: Optional[User] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)  # Convert Decimal to float for JSON serialization
        }


# Transaction Category
class TransactionCategoryCreate(BaseModel):
    """Schema for creating a new transaction category."""
    name: str = Field(..., min_length=1, max_length=100)


class TransactionCategory(BaseModel):
    category_id: int
    user_id: int
    name: str = Field(..., min_length=1, max_length=100)

    class Config:
        from_attributes = True


class TransactionCategoryUpdate(BaseModel):
    """Schema for updating a transaction category's name."""
    name: str = Field(..., min_length=1, max_length=100)


class ExistingCategory(BaseModel):
    type: Literal["existing"] = "existing" # Discriminator
    category_id: int


class NewCategory(BaseModel):
    type: Literal["new"] = "new" # Discriminator
    name: str = Field(..., min_length=1, max_length=100)


# Transaction
class TransactionCreate(BaseModel):
    """Schema for creating a new personal transaction (Request Body)."""
    category_input: Union[ExistingCategory, NewCategory] = Field(..., discriminator='type')

    # Define fields directly
    amount: Decimal = Field(..., gt=Decimal("0.0"))
    transaction_date: datetime
    notes: Optional[str] = None


class Transaction(BaseModel):
    """Schema for representing a personal transaction in responses."""
    # Repeat common fields
    category_id: Optional[int] = None
    amount: Decimal
    transaction_date: datetime
    notes: Optional[str]
    # Add output-specific fields
    transaction_id: int
    user_id: int
    created_at: datetime
    # Nest the category details
    category: Optional[TransactionCategory] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)  # Convert Decimal to float for JSON serialization
        }


class UserNetBalance(BaseModel):
    user_id: int
    username: str
    net_amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)  # Convert Decimal to float for JSON serialization
        }


class GroupBalanceSummary(BaseModel):
    group_id: int
    balances: list[UserNetBalance]

    class Config:
        from_attributes = True


class SuggestedPayment(BaseModel):
    payer: User
    payee: User
    amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)  # Convert Decimal to float for JSON serialization
        }


class SettlementSummary(BaseModel):
    group_id: int
    suggested_payments: list[SuggestedPayment]

    class Config:
        from_attributes = True


class UserToUserBalance(BaseModel):
    """
    Represents the net financial balance between user1 (typically the requester)
    and user2 (the other user) within a specific group.
    """
    user1: User
    user2: User
    group_id: int

    # Positive value: User1 owes User2 this amount.
    # Negative value: User2 owes User1 this amount.
    # Zero: They are settled to each other in this group
    net_amount_user1_owes_user2: Decimal
    suggested_settlement_amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)  # Convert Decimal to float for JSON serialization
        }

    
class Notification(BaseModel):
    id: int
    recipient_user_id: int
    message: str
    is_read: bool
    created_at: datetime
    notification_type: Optional[NotificationType] = None

    related_group_id: Optional[int] = None
    related_bill_id: Optional[int] = None
    related_payment_id: Optional[int] = None
    related_user_id: Optional[int] = None

    recipient: Optional[User] = None

    class Config:
        from_attributes = True


class UnreadNotificationCount(BaseModel):
    unread_count: int


# Audit log
class AuditLogEntryResponse(BaseModel):
    """
    Represents a single audit log entry for an activity feed.
    """
    id: int
    timestamp: datetime
    action_type: AuditActionType
    actor_user: Optional[User] = None

    display_message: str 

    group_id: Optional[int] = None
    target_bill_id: Optional[int] = None
    target_payment_id: Optional[int] = None
    target_user_id: Optional[int] = None

    class Config:
        from_attributes = True


class GroupActivityFeedResponse(BaseModel):
    """
    Represents the paginated activity feed for a group.
    """
    group_id: int # The group this feed is for
    activities: list[AuditLogEntryResponse]


class TransactionUpdate(BaseModel):
    """Schema for updating an existing transaction."""
    category_input: Optional[Union[ExistingCategory, NewCategory]] = Field(None, discriminator='type')
    amount: Optional[Decimal] = Field(None, gt=Decimal("0.0"))
    transaction_date: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class SimpleUserBalance(BaseModel):
    user: User
    balance: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(round(v, 2))
        }

# --- Friendship Schemas ---

class FriendshipBase(BaseModel):
    requester_id: int
    addressee_id: int
    status: FriendshipStatus

class FriendshipCreate(BaseModel):
    """Schema for creating a new friend request."""
    addressee_id: int

class FriendshipUpdate(BaseModel):
    """Schema for updating a friend request (e.g., accepting)."""
    status: FriendshipStatus # Can be constrained to 'accepted' in the endpoint

class Friendship(FriendshipBase):
    """Schema for representing a friendship in responses."""
    requester: User
    addressee: User
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Group Invitation Schemas ---

class GroupInvitationBase(BaseModel):
    group_id: int
    inviter_id: int
    invitee_id: int
    status: GroupInvitationStatus

class GroupInvitationCreate(BaseModel):
    """Schema for creating a new group invitation."""
    invitee_id: int
    # group_id will be a path parameter in the endpoint

class GroupInvitationUpdate(BaseModel):
    """Schema for responding to a group invitation."""
    status: GroupInvitationStatus # Can be constrained to 'accepted' or 'declined'

class GroupInvitation(BaseModel):
    """Schema for representing a group invitation in responses."""
    invitation_id: int
    status: GroupInvitationStatus
    group: Group # Nested Group schema
    inviter: User # Nested User schema
    invitee: User # Nested User schema
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GroupInvitationInfo(BaseModel):
    """Schema for representing a group invitation with nested info for responses."""
    invitation_id: int
    status: GroupInvitationStatus
    group: Group
    inviter: User

    class Config:
        from_attributes = True

class UserRoleResponse(BaseModel):
    role: GroupRole

class GroupMemberRoleUpdate(BaseModel):
    role: GroupRole

class GroupWithMembers(Group):
    members: List[GroupMember] = []


# Statistics
class SpendingByCategory(BaseModel):
    category_name: str
    total_amount: Decimal

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# Update forward references
Group.model_rebuild()
Bill.model_rebuild()

class UserFinancialBar(BaseModel):
    user_id: int
    username: str
    total_paid_out: Decimal
    total_owed_share: Decimal
    net_amount: Decimal

    class Config:
        from_attributes = True

class GroupFinancialBarSummary(BaseModel):
    group_id: int
    bars: list[UserFinancialBar]

    class Config:
        from_attributes = True