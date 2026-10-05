"""
reports.py
----------
Assembles the data-quality report, combining duplicate findings and business-rule violations across
all three master data object types, in one place — what a data steward
would actually pull up before a governance meeting.
"""

from dataclasses import dataclass

from .records import MasterDataset
from .business_rules import validate_customer, validate_vendor, validate_material, RuleViolation
from .duplicate_detection import (
    find_customer_duplicates, find_vendor_duplicates, find_material_duplicates, DuplicateGroup,
)


@dataclass
class DataQualityReport:
    customer_violations: dict[str, list[RuleViolation]]
    vendor_violations: dict[str, list[RuleViolation]]
    material_violations: dict[str, list[RuleViolation]]
    customer_duplicates: list[DuplicateGroup]
    vendor_duplicates: list[DuplicateGroup]
    material_duplicates: list[DuplicateGroup]

    @property
    def total_records_checked(self) -> int:
        return len(self.customer_violations) + len(self.vendor_violations) + len(self.material_violations)

    @property
    def total_records_with_errors(self) -> int:
        return sum(
            1
            for violations in (
                *self.customer_violations.values(),
                *self.vendor_violations.values(),
                *self.material_violations.values(),
            )
            if any(v.severity == "error" for v in violations)
        )

    @property
    def total_duplicate_groups(self) -> int:
        return len(self.customer_duplicates) + len(self.vendor_duplicates) + len(self.material_duplicates)


def run_data_quality_report(dataset: MasterDataset) -> DataQualityReport:
    customer_violations = {c.customer_id: validate_customer(c) for c in dataset.customers}
    vendor_violations = {v.vendor_id: validate_vendor(v) for v in dataset.vendors}
    material_violations = {m.material_id: validate_material(m) for m in dataset.materials}

    # Only keep entries that actually have violations — an empty list per
    # clean record would make the report noisy and harder to scan.
    customer_violations = {k: v for k, v in customer_violations.items() if v}
    vendor_violations = {k: v for k, v in vendor_violations.items() if v}
    material_violations = {k: v for k, v in material_violations.items() if v}

    return DataQualityReport(
        customer_violations=customer_violations,
        vendor_violations=vendor_violations,
        material_violations=material_violations,
        customer_duplicates=find_customer_duplicates(dataset.customers),
        vendor_duplicates=find_vendor_duplicates(dataset.vendors),
        material_duplicates=find_material_duplicates(dataset.materials),
    )
