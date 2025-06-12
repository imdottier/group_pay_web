from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.database import DbSessionDep
from backend.crud import (
    create_audit_log_entry
)
from backend.schemas import BillCreate, BillUpdate
import backend.models as models
from backend.models import AuditActionType
import logging

logger = logging.getLogger(__name__)

async def record_group_activity(
    db: AsyncSession,
    actor_user: Optional[models.User],
    action_type: AuditActionType,
    group_id: int,
    target_role: Optional[models.GroupRole] = None,
    target_bill: Optional[models.Bill] = None,
    target_payment: Optional[models.Payment] = None,
    target_user_membership_related: Optional[models.User] = None,
):
    """
    Service function to create an audit log entry for a group activity.
    Constructs a meaningful summary message.
    """
    actor_user_id = actor_user.user_id if actor_user else None
    actor_name = actor_user.username if actor_user and actor_user.username else "System"

    target_bill_id = target_bill.bill_id if target_bill else None
    target_payment_id = target_payment.payment_id if target_payment else None
    target_user_id_for_log = target_user_membership_related.user_id if target_user_membership_related else None
    
    summary = f"{actor_name} performed {action_type.value}" # Default

    # Construct more specific summary messages
    if action_type == AuditActionType.bill_created and target_bill:
        summary = f"{actor_name} created bill '{target_bill.title}'."
    elif action_type == AuditActionType.bill_updated and target_bill:
        summary = f"{actor_name} updated bill '{target_bill.title}'."
    elif action_type == AuditActionType.bill_deleted and target_bill: # Assumes target_bill might be passed before deletion
        summary = f"{actor_name} deleted bill '{target_bill.title}' (ID: {target_bill_id})."
    
    elif action_type == AuditActionType.payment_created and target_payment:
        payee_info = f"to user ID {target_payment.payee_id}"

        payee = target_user_membership_related
        if payee:
            payee_info = f"to {payee.username}"
        summary = f"{actor_name} recorded a payment of {target_payment.amount:,.0f} VND {payee_info}."
    
    elif action_type == AuditActionType.member_added and target_user_membership_related:
        member_name = target_user_membership_related.username or f"User ID {target_user_membership_related.user_id}"
        if actor_user and actor_user.user_id != target_user_membership_related.user_id:
            summary = f"{actor_name} added {member_name} to the group."
        else:
            summary = f"{member_name} joined the group."
    elif action_type == AuditActionType.member_invited and target_user_membership_related:
        member_name = target_user_membership_related.username or f"User ID {target_user_membership_related.user_id}"
        if actor_user and actor_user.user_id != target_user_membership_related.user_id:
            summary = f"{actor_name} invited {member_name} to the group."
        else:
            summary = f"{member_name} joined the group."
    elif action_type == AuditActionType.member_removed and target_user_membership_related:
        member_name = target_user_membership_related.username or f"User ID {target_user_membership_related.user_id}"
        summary = f"{actor_name} removed {member_name} from the group."
    elif action_type == AuditActionType.member_left:
        summary = f"{actor_name} left the group."
    elif action_type == AuditActionType.member_role_promoted and target_user_membership_related:
        member_name = target_user_membership_related.username or f"User ID {target_user_membership_related.user_id}"
        summary = f"{actor_name} promoted {member_name} to {target_role.value}"
    elif action_type == AuditActionType.member_role_demoted and target_user_membership_related:
        member_name = target_user_membership_related.username or f"User ID {target_user_membership_related.user_id}"
        summary = f"{actor_name} demoted {member_name} to {target_role.value}"

    elif action_type == AuditActionType.group_created:
        summary = f"{actor_name} created the group."
    elif action_type == AuditActionType.group_details_updated:
        summary = f"{actor_name} updated group details."
    # ... add more message formatting for other AuditActionTypes ...

    await create_audit_log_entry( # The low-level DB insert
        db=db,
        actor_user_id=actor_user_id,
        action_type=action_type,
        group_id=group_id,
        target_bill_id=target_bill_id,
        target_payment_id=target_payment_id,
        target_user_id=target_user_id_for_log,
        summary_message=summary
    )
    # The commit is handled by the calling service function (e.g., create_bill_service)