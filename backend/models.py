from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, DateTime, func, Enum as SqlEnum
from sqlalchemy import CheckConstraint, UniqueConstraint, ForeignKeyConstraint, Date, Text, Boolean
from sqlalchemy.orm import relationship

# IMPORTANT: Import the Base from your database setup file!
from backend.database import Base
from enum import Enum as PyEnum

class GroupRole(PyEnum):
    owner = "owner"
    admin = "admin"
    member = "member"
    

# Define your first table as a Python class
class User(Base):
    __tablename__ = "users"  # The actual table name in the database
    __table_args__ = (
        UniqueConstraint('google_id', name='uq_google_id'),
        # Add other constraints if needed, e.g., UniqueConstraint('email') is handled by unique=True on column
    )

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=True) # Can be null for OAuth users initially
    full_name = Column(String(100), nullable=True)

    # Authentication
    google_id = Column(String(255), nullable=True, index=True) # Indexed for fast lookup during Google login
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    profile_image_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Example relationship (optional for now)
    memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    # Changed cascade for bills created by user - less aggressive
    bills_created = relationship("Bill", back_populates="bill_creator", foreign_keys="Bill.created_by") # Renamed for clarity, removed cascade
    bill_item_splits = relationship("BillItemSplit", back_populates="user", cascade="all, delete-orphan") # Renamed for clarity
    bill_parts = relationship("BillPart", back_populates="user", cascade="all, delete-orphan") # Renamed for clarity

    # Collection of Payments where this user is the PAYER
    payments_made = relationship(
        "Payment",
        back_populates="payer",           # Links back to Payment.payer
        foreign_keys="Payment.payer_id"   # Specifies FK column on Payment table
                                          # Cascade usually not needed due to RESTRICT on DB FK
    )

    # Collection of Payments where this user is the PAYEE
    payments_received = relationship(
        "Payment",
        back_populates="payee",           # Links back to Payment.payee
        foreign_keys="Payment.payee_id"   # Specifies FK column on Payment table
                                          # Cascade usually not needed due to RESTRICT on DB FK
    )

    transactions = relationship("Transaction", back_populates="user")


# Define another table
class Group(Base):
    __tablename__ = "users_groups"

    group_id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String(100), index=True)
    description = Column(String(255))

    # Example relationship (optional for now)
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    bills = relationship("Bill", back_populates="group", cascade="all, delete-orphan")
    bill_categories = relationship("BillCategory", back_populates="group", cascade="all, delete-orphan")


# Add any other tables you need here, inheriting from Base
class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint('group_id', 'user_id', name='uq_group_user'),
    )

    group_id = Column(Integer, ForeignKey("users_groups.group_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)

    role = Column(SqlEnum(GroupRole), default=GroupRole.member, nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    left_at = Column(DateTime(timezone=True), nullable=True)

    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="memberships")


class SplitMethod(PyEnum):
    item = "item"
    percentage = "percentage"
    equal = "equal"
    exact = "exact"


class BillCategory(Base):
    __tablename__ = "bill_categories"
    __table_args__ = (
        UniqueConstraint('group_id', 'name', name='uq_group_category_name'),
    )

    category_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    group_id = Column(Integer, ForeignKey("users_groups.group_id", ondelete="CASCADE"), nullable=True) # Null for default categories

    group = relationship("Group", back_populates="bill_categories")
    bills = relationship("Bill", back_populates="category")


class Bill(Base):
    __tablename__ = "bills"

    bill_id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("users_groups.group_id", ondelete="CASCADE"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    category_id = Column(Integer, ForeignKey("bill_categories.category_id", ondelete="SET NULL"), nullable=True)
    title = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    total_amount = Column(Numeric(10, 2), nullable=False)
    receipt_image_url = Column(String(255), nullable=True)
    split_method = Column(SqlEnum(SplitMethod), default=SplitMethod.equal, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    group = relationship("Group", back_populates="bills")
    category = relationship("BillCategory", back_populates="bills")
    bill_creator = relationship("User", back_populates="bills_created", foreign_keys=[created_by])
    bill_parts = relationship("BillPart", back_populates="bill", cascade="all, delete-orphan")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")
    initial_payments = relationship("InitialPayment", back_populates="bill", cascade="all, delete-orphan")


# Add initial payment
class InitialPayment(Base):
    __tablename__ = "initial_payments"
    __table_args__ = (
        CheckConstraint('amount_paid > 0', name="check_initial_payment_positive"),
    )

    bill_id = Column(Integer, ForeignKey("bills.bill_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True)
    amount_paid = Column(Numeric(10, 2), nullable=False)

    # Relationships
    bill = relationship("Bill", back_populates="initial_payments")
    user = relationship("User")


class BillItem(Base):
    __tablename__ = "bill_items"
    __table_args__ = (
        CheckConstraint('quantity > 0', name="check_quantity_positive"),
    )

    bill_id = Column(Integer, ForeignKey("bills.bill_id", ondelete="CASCADE"), primary_key=True)
    item_id = Column(Integer, primary_key=True)

    name = Column(String(255), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)

    # Relationships
    bill_item_splits = relationship("BillItemSplit", back_populates="bill_item", cascade="all, delete-orphan")
    bill = relationship("Bill", back_populates="items")


class BillItemSplit(Base):
    __tablename__ = "bill_item_split"
    # Define constraints in __table_args__
    __table_args__ = (
        # Composite Foreign Key referencing bill_items table
        ForeignKeyConstraint(
            ['bill_id', 'item_id'],
            ['bill_items.bill_id', 'bill_items.item_id'],
            ondelete="CASCADE", # Added ondelete
            name='fk_bill_item_split_item' # Optional: constraint name
        ),
        # Check constraint for quantity
        CheckConstraint('quantity > 0', name="check_split_quantity_positive"),
        # Optional: Explicit PK naming if desired
        # PrimaryKeyConstraint('bill_id', 'item_id', 'user_id', name='pk_bill_item_split')
    )

    bill_id = Column(Integer, primary_key=True)
    item_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"), primary_key=True)
    
    # Data
    quantity = Column(Integer, nullable=False)

    # Relationships for easier access to related data (optional)
    bill_item = relationship("BillItem", back_populates="bill_item_splits")
    user = relationship("User", back_populates="bill_item_splits")


class BillPart(Base):
    __tablename__ = "bill_part"
    __table_args__ = (
        # Check constraint for amount
        CheckConstraint('amount_owed >= 0', name="check_amount_owed_positive"),
        # Optional: Explicit PK naming if desired
        # PrimaryKeyConstraint('bill_id', 'user_id', name='pk_bill_part')
    )

    # Primary Key
    bill_id = Column(Integer, ForeignKey('bills.bill_id', ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"), primary_key=True)
    
    # Data
    amount_owed = Column(Numeric(10, 2), nullable=False)

    # Relationships for easier access to related data (optional)
    bill = relationship("Bill", back_populates="bill_parts")
    user = relationship("User", back_populates="bill_parts")


class Payment(Base):
    __tablename__ = "payments"
    __table__args__ = (
        CheckConstraint('amount > 0', name="check_payment_amount_positive")
    )

    payment_id = Column(Integer, primary_key=True)

    group_id = Column(Integer, ForeignKey('users_groups.group_id', ondelete="RESTRICT"))
    payer_id = Column(Integer, ForeignKey('users.user_id', ondelete="RESTRICT"))
    payee_id = Column(Integer, ForeignKey('users.user_id', ondelete="RESTRICT"))
    bill_id = Column(Integer, ForeignKey('bills.bill_id', ondelete="SET NULL"), nullable=True)
    
    payment_date = Column(Date, nullable=False, default=func.now())
    notes = Column(Text, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Optional: Link to Group (assuming Group doesn't need Payment list)
    group = relationship("Group") # Add back_populates if Group.payments is defined

    # Link to Payer User - Use foreign_keys AND back_populates
    payer = relationship("User", back_populates="payments_made",  # Links to User.payments_made
                         foreign_keys=[payer_id])         # Specifies FK column for this relationship

    # Link to Payee User - Use foreign_keys AND back_populates
    payee = relationship("User", back_populates="payments_received", # Links to User.payments_received
                         foreign_keys=[payee_id])          # Specifies FK column for this relationship

    # Optional: Link to Bill (assuming Bill doesn't need Payment list)
    bill = relationship("Bill") # Add back_populates if Bill.payments is defined


class TransactionCategory(Base):
    __tablename__ = "transaction_categories"
    __table_args__ = (
        # User cannot have two categories with the same name
        UniqueConstraint('user_id', 'name', name='uq_user_category_name'),
    )
    
    category_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)

    # Relationship to transactions using this category
    transactions = relationship("Transaction", back_populates="category") # Added relationship


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint('amount > 0', name="check_transaction_amount_positive"),
    )

    transaction_id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey('transaction_categories.category_id', ondelete="SET NULL"), nullable=True)
    
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_date = Column(Date, nullable=False, default=func.now())
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Relationships ---
    user = relationship("User", back_populates="transactions") # Add back_populates="transactions" to User if needed
    category = relationship("TransactionCategory", back_populates="transactions") # Added relationship


class NotificationType(PyEnum): # Optional: If you want to categorize notifications
    GROUP_INVITE = "group_invite"
    NEW_BILL = "new_bill"
    BILL_UPDATE = "bill_update"
    MEMBER_ADDED_TO_GROUP = "member_added_to_group"
    FRIEND_REQUEST = "friend_request"
    FRIEND_REQUEST_ACCEPTED = "friend_request_accepted"
    BILL_PAYMENT_REMINDER = "payment_reminder"
    TRANSACTION_REMINDER = "transaction_reminder"
    # ... add more types as needed

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    
    recipient_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    notification_type = Column(SqlEnum(NotificationType), nullable=True) # Helpful for FE rendering/logic
    
    # Link to relevant entities (make these nullable as not all notifications link to all entities)
    related_group_id = Column(Integer, ForeignKey("users_groups.group_id", ondelete="SET NULL"), nullable=True, index=True)
    related_bill_id = Column(Integer, ForeignKey("bills.bill_id", ondelete="SET NULL"), nullable=True, index=True)
    related_payment_id = Column(Integer, ForeignKey("payments.payment_id", ondelete="SET NULL"), nullable=True, index=True)
    related_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships (optional, for ORM access if needed, but often notifications are read flatly)
    recipient = relationship("User", foreign_keys=[recipient_user_id])
    # related_group = relationship("Group")
    # related_bill = relationship("Bill")
    # related_payment = relationship("Payment")
    # related_user = relationship("User", foreign_keys=[related_user_id])


class AuditActionType(PyEnum):
    # Bill actions
    bill_created = "bill_created"
    bill_updated = "bill_updated"
    bill_deleted = "bill_deleted"
    # Payment actions
    payment_created = "payment_created"
    payment_updated = "payment_updated"
    payment_deleted = "payment_deleted"
    # Group membership actions
    member_invited = "member_invited" # If you add invites
    member_added = "member_added"   # Could be from invite or direct add
    member_left = "member_left"     # User initiated
    member_removed = "member_removed" # Admin/owner initiated
    member_role_promoted = "member_role_promoted"
    member_role_demoted = "member_role_demoted"
    # Group actions
    group_created = "group_created"
    group_details_updated = "group_details_updated"
    # Other actions


class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    actor_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True) # Null if system action
    action_type = Column(SqlEnum(AuditActionType), nullable=False, index=True)
    
    group_id = Column(Integer, ForeignKey("users_groups.group_id", ondelete="CASCADE"), nullable=True, index=True)

    # Target entities (store IDs of relevant objects)
    target_bill_id = Column(Integer, ForeignKey("bills.bill_id", ondelete="SET NULL"), nullable=True, index=True)
    target_payment_id = Column(Integer, ForeignKey("payments.payment_id", ondelete="SET NULL"), nullable=True, index=True) # Adjust FK
    # For member actions, this is the user whose membership changed
    target_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True) 
                                                                                                
    # Store a summary or details of the change
    # For simple messages:
    summary_message = Column(String(512), nullable=True) # "User X updated bill Y's amount."
    
    # For structured details (more flexible for programmatic use, but more complex to query/store):
    # details_json = Column(JSON, nullable=True) 
    # e.g., {"old_value": {"amount": 100}, "new_value": {"amount": 120}} for an update
    # e.g., {"removed_user_id": Z, "reason": "spam"}
    # e.g., {"old_role": "member", "new_role": "admin"}

    # Relationships (optional, primarily for if you ever query AuditLogEntry ORM and want to join)
    actor = relationship("User", foreign_keys=[actor_user_id], lazy="joined")
    # group = relationship("Group")
    # target_bill = relationship("Bill")
    # target_payment = relationship("Payment")
    # target_user = relationship("User", foreign_keys=[target_user_id])


class FriendshipStatus(PyEnum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    # DECLINED/BLOCKED could be added later if needed

class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint('requester_id', 'addressee_id', name='uq_friendship'),
    )

    requester_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    addressee_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    
    # The user who initiated the request. Not strictly needed with the check constraint,
    # but can be useful for tracking who sent the last status update.
    # For a simple pending/accepted system, it's less critical.
    # We can derive who sent the request from the status transition log if we had one.

    status = Column(SqlEnum(FriendshipStatus), nullable=False, default=FriendshipStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    requester = relationship("User", foreign_keys=[requester_id])
    addressee = relationship("User", foreign_keys=[addressee_id])


class GroupInvitationStatus(PyEnum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"

class GroupInvitation(Base):
    __tablename__ = "group_invitations"
    __table_args__ = (
        UniqueConstraint('group_id', 'invitee_id', name='uq_group_invitation'),
    )

    invitation_id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("users_groups.group_id", ondelete="CASCADE"), nullable=False)
    inviter_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    invitee_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    status = Column(SqlEnum(GroupInvitationStatus), nullable=False, default=GroupInvitationStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    group = relationship("Group")
    inviter = relationship("User", foreign_keys=[inviter_id])
    invitee = relationship("User", foreign_keys=[invitee_id])