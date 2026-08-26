"""
records.py
----------
The three master data object types this posting names explicitly:
customer, vendor, and material. Modeled with the fields a real SAP-style
master data governance process actually cares about — not a generic
"name/id" toy model, but the specific fields duplicate-detection and
business-rule validation need (tax ID, address, payment terms, unit of
measure, etc.), since those are exactly where real master-data quality
problems show up.

This is a SYNTHETIC domain model, not read from or connected to any real
ERP/SAP system — see the project README for the full disclosure.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class RecordStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"  # e.g. a vendor under compliance review
    MARKED_FOR_DELETION = "marked_for_deletion"


@dataclass
class CustomerRecord:
    customer_id: str
    name: str
    country_code: str  # ISO 3166-1 alpha-2, e.g. "DE"
    vat_id: str | None  # EU VAT ID, e.g. "DE123456789" — required for EU customers
    street: str
    city: str
    postal_code: str
    status: RecordStatus = RecordStatus.ACTIVE
    created_on: date | None = None


@dataclass
class VendorRecord:
    vendor_id: str
    name: str
    country_code: str
    vat_id: str | None
    street: str
    city: str
    postal_code: str
    payment_terms_days: int  # e.g. 30 (net-30)
    status: RecordStatus = RecordStatus.ACTIVE
    created_on: date | None = None


@dataclass
class MaterialRecord:
    material_id: str
    description: str
    material_group: str  # e.g. "RAW-METAL", "PACK-MAT"
    base_unit_of_measure: str  # e.g. "KG", "EA", "L"
    standard_price_eur: float | None
    status: RecordStatus = RecordStatus.ACTIVE
    created_on: date | None = None


@dataclass
class MasterDataset:
    customers: list[CustomerRecord] = field(default_factory=list)
    vendors: list[VendorRecord] = field(default_factory=list)
    materials: list[MaterialRecord] = field(default_factory=list)
