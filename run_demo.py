"""
run_demo.py
-----------
Runs the full master-data-governance workbench end to end against the
seed dataset: a data-quality report (duplicates + rule violations),
followed by a walkthrough of three change requests (one clean CREATE,
one UPDATE that gets rejected on a business rule, one that breaches the
SLA) — printing the resulting audit trail.

Usage: python3 run_demo.py
"""

from datetime import date, datetime

from src.seed_data import build_seed_dataset
from src.reports import run_data_quality_report
from src.change_requests import (
    GovernanceWorkbench, ChangeRequest, RequestType, ObjectType, RequestStatus, ServiceLevelBreach,
)
from src.records import CustomerRecord, VendorRecord


def print_report(report):
    print("=" * 70)
    print("DATA QUALITY REPORT")
    print("=" * 70)
    print(f"\nRecords checked (all objects): {len(report.customer_violations) + len(report.vendor_violations) + len(report.material_violations)} with violations")
    print(f"Records with blocking errors: {report.total_records_with_errors}")
    print(f"Duplicate groups found: {report.total_duplicate_groups}\n")

    print("-- Business rule violations --")
    for label, violations_by_id in (
        ("Customers", report.customer_violations),
        ("Vendors", report.vendor_violations),
        ("Materials", report.material_violations),
    ):
        for record_id, violations in violations_by_id.items():
            for v in violations:
                print(f"  [{v.severity.upper():7}] {label[:-1]} {record_id}: {v.rule_id} — {v.message}")

    print("\n-- Duplicate groups --")
    for label, groups in (
        ("Customer", report.customer_duplicates),
        ("Vendor", report.vendor_duplicates),
        ("Material", report.material_duplicates),
    ):
        for g in groups:
            print(f"  {label} duplicate ({g.match_basis}): {g.record_ids} matched on '{g.match_key}'")


def main():
    dataset = build_seed_dataset()
    report = run_data_quality_report(dataset)
    print_report(report)

    print("\n" + "=" * 70)
    print("CHANGE REQUEST WALKTHROUGH")
    print("=" * 70)

    workbench = GovernanceWorkbench(dataset)

    # 1. A clean CREATE — should validate and apply without issue.
    clean_request = ChangeRequest(
        request_id="CR-0001",
        object_type=ObjectType.CUSTOMER,
        request_type=RequestType.CREATE,
        record=CustomerRecord("CUST-2001", "Skandia Metalworks AB", "SE", "SE112233445", "Verkstadsvagen 2", "Malmö", "21119"),
        submitted_by="j.schmidt",
        submitted_on=date(2026, 8, 10),
    )
    workbench.process(clean_request, datetime(2026, 8, 10, 9, 0))
    print(f"\nCR-0001 (clean CREATE): status={clean_request.status.value}")

    # 2. An UPDATE that violates a business rule — should be rejected.
    bad_request = ChangeRequest(
        request_id="CR-0002",
        object_type=ObjectType.VENDOR,
        request_type=RequestType.UPDATE,
        record=VendorRecord("VEND-2001", "Stahlwerk Nord GmbH", "DE", None, "Industriering 3", "Essen", "45127", 30),
        submitted_by="a.weber",
        submitted_on=date(2026, 8, 11),
    )
    workbench.process(bad_request, datetime(2026, 8, 11, 14, 30))
    print(f"CR-0002 (EU vendor, VAT ID removed): status={bad_request.status.value}, violations={[v.rule_id for v in bad_request.violations]}")

    # 3. A request that breaches SLA (submitted, never resolved, checked 5 days later).
    stale_request = ChangeRequest(
        request_id="CR-0003",
        object_type=ObjectType.MATERIAL,
        request_type=RequestType.CREATE,
        record=None,  # not applied in this demo — SLA check happens pre-processing
        submitted_by="m.fischer",
        submitted_on=date(2026, 8, 5),
    )
    workbench.submit(stale_request, datetime(2026, 8, 5, 10, 0))
    try:
        workbench.check_sla(stale_request, now=datetime(2026, 8, 10, 10, 0))
    except ServiceLevelBreach as e:
        print(f"CR-0003 SLA check: BREACHED — {e}")

    print("\n" + "-" * 70)
    print("AUDIT TRAIL")
    print("-" * 70)
    for entry in workbench.audit_log():
        print(f"  {entry.timestamp.isoformat()} | {entry.request_id} | {entry.event:10} | {entry.detail}")

    print("\nDone.")


if __name__ == "__main__":
    main()
