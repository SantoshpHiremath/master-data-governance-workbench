"""
change_requests.py
--------------------
Models the posting's "execute routine data maintenance requests, creating
or updating records according to established procedures and service
levels" and "document data maintenance activities and report on the
status of assigned tasks" tasks.

A ChangeRequest goes through an explicit state machine (SUBMITTED ->
VALIDATED -> APPLIED, or REJECTED at the validation step) rather than
being applied directly — this models a real data-steward workflow where
a request is checked against business rules BEFORE it touches the master
dataset, and every request leaves an audit-trail entry regardless of
outcome (a governance process needs to show what was requested and why
it was accepted or rejected, not just the end state of the data).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Callable

from .records import CustomerRecord, VendorRecord, MaterialRecord, MasterDataset
from .business_rules import validate_customer, validate_vendor, validate_material, RuleViolation


class RequestStatus(str, Enum):
    SUBMITTED = "submitted"
    VALIDATED = "validated"
    APPLIED = "applied"
    REJECTED = "rejected"


class RequestType(str, Enum):
    CREATE = "create"
    UPDATE = "update"


class ObjectType(str, Enum):
    CUSTOMER = "customer"
    VENDOR = "vendor"
    MATERIAL = "material"


@dataclass
class ChangeRequest:
    request_id: str
    object_type: ObjectType
    request_type: RequestType
    record: CustomerRecord | VendorRecord | MaterialRecord
    submitted_by: str
    submitted_on: date
    status: RequestStatus = RequestStatus.SUBMITTED
    violations: list[RuleViolation] = field(default_factory=list)
    applied_on: date | None = None


@dataclass(frozen=True)
class AuditEntry:
    request_id: str
    timestamp: datetime
    event: str  # "submitted" | "validated" | "applied" | "rejected"
    detail: str


class ServiceLevelBreach(Exception):
    """Raised when a request's age exceeds the configured SLA and hasn't
    reached a terminal state (APPLIED or REJECTED)."""


_VALIDATORS: dict[ObjectType, Callable] = {
    ObjectType.CUSTOMER: validate_customer,
    ObjectType.VENDOR: validate_vendor,
    ObjectType.MATERIAL: validate_material,
}

# "Established procedures and service levels" — a routine data
# maintenance request should be resolved within this many days.
DEFAULT_SLA_DAYS = 3


class GovernanceWorkbench:
    """
    Orchestrates the change-request lifecycle against a MasterDataset,
    producing an audit trail as a side effect of every state transition
    (not reconstructed after the fact from the final data state, which
    would lose the "why" — the actual governance-relevant information).
    """

    def __init__(self, dataset: MasterDataset):
        self.dataset = dataset
        self._audit_log: list[AuditEntry] = []

    def submit(self, request: ChangeRequest, now: datetime) -> None:
        if request.status != RequestStatus.SUBMITTED:
            raise ValueError(f"Request {request.request_id} is not in SUBMITTED state")
        self._audit_log.append(
            AuditEntry(request.request_id, now, "submitted",
                       f"{request.request_type.value} {request.object_type.value} submitted by {request.submitted_by}")
        )

    def validate(self, request: ChangeRequest, now: datetime) -> list[RuleViolation]:
        validator = _VALIDATORS[request.object_type]
        violations = validator(request.record)
        request.violations = violations

        blocking = [v for v in violations if v.severity == "error"]
        if blocking:
            request.status = RequestStatus.REJECTED
            self._audit_log.append(
                AuditEntry(request.request_id, now, "rejected",
                           f"{len(blocking)} blocking violation(s): " + "; ".join(v.rule_id for v in blocking))
            )
        else:
            request.status = RequestStatus.VALIDATED
            warn_note = f" ({len(violations)} warning(s) noted)" if violations else ""
            self._audit_log.append(
                AuditEntry(request.request_id, now, "validated", f"passed validation{warn_note}")
            )
        return violations

    def apply(self, request: ChangeRequest, now: datetime) -> None:
        if request.status != RequestStatus.VALIDATED:
            raise ValueError(
                f"Request {request.request_id} must be VALIDATED before it can be applied "
                f"(current status: {request.status.value})"
            )

        target_list = {
            ObjectType.CUSTOMER: self.dataset.customers,
            ObjectType.VENDOR: self.dataset.vendors,
            ObjectType.MATERIAL: self.dataset.materials,
        }[request.object_type]
        id_field = {
            ObjectType.CUSTOMER: "customer_id",
            ObjectType.VENDOR: "vendor_id",
            ObjectType.MATERIAL: "material_id",
        }[request.object_type]

        record_id = getattr(request.record, id_field)
        existing_index = next(
            (i for i, r in enumerate(target_list) if getattr(r, id_field) == record_id), None
        )

        if request.request_type == RequestType.CREATE:
            if existing_index is not None:
                raise ValueError(f"Cannot CREATE {record_id}: a record with this ID already exists")
            target_list.append(request.record)
        else:  # UPDATE
            if existing_index is None:
                raise ValueError(f"Cannot UPDATE {record_id}: no existing record with this ID")
            target_list[existing_index] = request.record

        request.status = RequestStatus.APPLIED
        request.applied_on = now.date()
        self._audit_log.append(
            AuditEntry(request.request_id, now, "applied",
                       f"{request.request_type.value} applied to {request.object_type.value} {record_id}")
        )

    def process(self, request: ChangeRequest, now: datetime) -> list[RuleViolation]:
        """Convenience: submit -> validate -> (apply if validated).
        Returns the violations found (empty list if the request passed
        cleanly and was applied)."""
        self.submit(request, now)
        violations = self.validate(request, now)
        if request.status == RequestStatus.VALIDATED:
            self.apply(request, now)
        return violations

    def audit_log(self) -> list[AuditEntry]:
        return list(self._audit_log)

    def check_sla(self, request: ChangeRequest, now: datetime, sla_days: int = DEFAULT_SLA_DAYS) -> None:
        """Raises ServiceLevelBreach if a non-terminal request has been
        open longer than the SLA. Terminal requests (APPLIED/REJECTED)
        never breach, regardless of age — the SLA is about resolution
        time, not a request's total lifespan."""
        if request.status in (RequestStatus.APPLIED, RequestStatus.REJECTED):
            return
        age_days = (now.date() - request.submitted_on).days
        if age_days > sla_days:
            raise ServiceLevelBreach(
                f"Request {request.request_id} has been open {age_days} days, "
                f"exceeding the {sla_days}-day SLA (status: {request.status.value})"
            )
