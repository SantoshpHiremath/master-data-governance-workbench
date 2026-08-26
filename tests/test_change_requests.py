from datetime import date, datetime

import pytest

from src.records import CustomerRecord, VendorRecord, MaterialRecord, MasterDataset
from src.change_requests import (
    GovernanceWorkbench, ChangeRequest, RequestType, ObjectType, RequestStatus, ServiceLevelBreach,
)


def empty_dataset():
    return MasterDataset()


class TestSubmitValidateApplyFlow:
    def test_clean_create_request_reaches_applied_status(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR1", ObjectType.CUSTOMER, RequestType.CREATE,
            CustomerRecord("C1", "Acme GmbH", "DE", "DE123456789", "Str 1", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        assert req.status == RequestStatus.APPLIED
        assert dataset.customers[0].customer_id == "C1"

    def test_request_with_blocking_violation_is_rejected_and_not_applied(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR2", ObjectType.CUSTOMER, RequestType.CREATE,
            CustomerRecord("C1", "Acme GmbH", "ZZ", None, "Str 1", "Berlin", "10115"),  # bad country code
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        assert req.status == RequestStatus.REJECTED
        assert dataset.customers == []  # must NOT have been applied

    def test_request_with_only_warnings_still_gets_applied(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR3", ObjectType.VENDOR, RequestType.CREATE,
            VendorRecord("V1", "Acme Vendor", "DE", "DE123456789", "Str 1", "Berlin", "10115", 200),  # warning-level payment terms
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        assert req.status == RequestStatus.APPLIED
        assert len(req.violations) == 1
        assert req.violations[0].severity == "warning"

    def test_create_fails_if_id_already_exists(self):
        dataset = MasterDataset(customers=[CustomerRecord("C1", "Existing", "DE", "DE123456789", "Str", "Berlin", "10115")])
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR4", ObjectType.CUSTOMER, RequestType.CREATE,
            CustomerRecord("C1", "Duplicate ID Attempt", "DE", "DE123456789", "Str", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        wb.submit(req, datetime(2026, 1, 1, 9, 0))
        wb.validate(req, datetime(2026, 1, 1, 9, 0))
        with pytest.raises(ValueError, match="already exists"):
            wb.apply(req, datetime(2026, 1, 1, 9, 0))

    def test_update_fails_if_id_does_not_exist(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR5", ObjectType.CUSTOMER, RequestType.UPDATE,
            CustomerRecord("C-NONEXISTENT", "Nobody", "DE", "DE123456789", "Str", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        wb.submit(req, datetime(2026, 1, 1, 9, 0))
        wb.validate(req, datetime(2026, 1, 1, 9, 0))
        with pytest.raises(ValueError, match="no existing record"):
            wb.apply(req, datetime(2026, 1, 1, 9, 0))

    def test_update_replaces_the_existing_record_not_appends(self):
        dataset = MasterDataset(customers=[CustomerRecord("C1", "Old Name", "DE", "DE123456789", "Str", "Berlin", "10115")])
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR6", ObjectType.CUSTOMER, RequestType.UPDATE,
            CustomerRecord("C1", "New Name", "DE", "DE123456789", "Str", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        assert len(dataset.customers) == 1
        assert dataset.customers[0].name == "New Name"

    def test_apply_before_validate_raises(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR7", ObjectType.CUSTOMER, RequestType.CREATE,
            CustomerRecord("C1", "Acme", "DE", "DE123456789", "Str", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        with pytest.raises(ValueError, match="must be VALIDATED"):
            wb.apply(req, datetime(2026, 1, 1, 9, 0))


class TestAuditTrail:
    def test_every_state_transition_produces_an_audit_entry(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR8", ObjectType.CUSTOMER, RequestType.CREATE,
            CustomerRecord("C1", "Acme", "DE", "DE123456789", "Str", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        events = [e.event for e in wb.audit_log()]
        assert events == ["submitted", "validated", "applied"]

    def test_rejected_request_produces_rejected_audit_entry_not_applied(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR9", ObjectType.CUSTOMER, RequestType.CREATE,
            CustomerRecord("C1", "Acme", "ZZ", None, "Str", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        events = [e.event for e in wb.audit_log()]
        assert events == ["submitted", "rejected"]

    def test_audit_log_is_a_copy_not_a_live_reference(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        log1 = wb.audit_log()
        req = ChangeRequest(
            "CR10", ObjectType.CUSTOMER, RequestType.CREATE,
            CustomerRecord("C1", "Acme", "DE", "DE123456789", "Str", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        # The snapshot taken before processing must not have grown.
        assert log1 == []
        assert len(wb.audit_log()) == 3


class TestServiceLevel:
    def test_request_within_sla_does_not_raise(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR11", ObjectType.MATERIAL, RequestType.CREATE,
            MaterialRecord("M1", "Widget", "RAW-METAL", "EA", 1.0),
            "tester", date(2026, 1, 1),
        )
        wb.submit(req, datetime(2026, 1, 1, 9, 0))
        wb.check_sla(req, now=datetime(2026, 1, 2, 9, 0))  # 1 day later, within default 3-day SLA

    def test_request_past_sla_raises(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR12", ObjectType.MATERIAL, RequestType.CREATE,
            MaterialRecord("M1", "Widget", "RAW-METAL", "EA", 1.0),
            "tester", date(2026, 1, 1),
        )
        wb.submit(req, datetime(2026, 1, 1, 9, 0))
        with pytest.raises(ServiceLevelBreach):
            wb.check_sla(req, now=datetime(2026, 1, 10, 9, 0))

    def test_applied_request_never_breaches_sla_regardless_of_age(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR13", ObjectType.MATERIAL, RequestType.CREATE,
            MaterialRecord("M1", "Widget", "RAW-METAL", "EA", 1.0),
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        # Should not raise even though this is checked long after submission.
        wb.check_sla(req, now=datetime(2026, 6, 1, 9, 0))

    def test_rejected_request_never_breaches_sla(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR14", ObjectType.CUSTOMER, RequestType.CREATE,
            CustomerRecord("C1", "Acme", "ZZ", None, "Str", "Berlin", "10115"),
            "tester", date(2026, 1, 1),
        )
        wb.process(req, datetime(2026, 1, 1, 9, 0))
        wb.check_sla(req, now=datetime(2026, 6, 1, 9, 0))

    def test_custom_sla_days_respected(self):
        dataset = empty_dataset()
        wb = GovernanceWorkbench(dataset)
        req = ChangeRequest(
            "CR15", ObjectType.MATERIAL, RequestType.CREATE,
            MaterialRecord("M1", "Widget", "RAW-METAL", "EA", 1.0),
            "tester", date(2026, 1, 1),
        )
        wb.submit(req, datetime(2026, 1, 1, 9, 0))
        # 2 days later: within a 1-day SLA, this should breach.
        with pytest.raises(ServiceLevelBreach):
            wb.check_sla(req, now=datetime(2026, 1, 3, 9, 0), sla_days=1)
