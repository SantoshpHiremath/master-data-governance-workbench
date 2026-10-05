# Master Data Governance Workbench

A tested Python project modeling the daily workflow of a master data governance role: cleansing and validating customer, vendor, and material records, running duplicate and inconsistency reports, executing data-maintenance requests against documented business rules and service levels, and producing an audit trail, all in a runnable system.

## What it does

- **`src/records.py`**: the three master data object types (customer, vendor, material), with the fields master-data quality work depends on (VAT ID, address, payment terms, unit of measure), not a generic id/name model.
- **`src/business_rules.py`**: documented data standards, business rules, and process workflows. Each rule is a small, named, independently testable function (for example "EU customers require a VAT ID on file"), which is the documentation: a governance reviewer can read the file top to bottom as the current rule set, with no separate document that can drift out of sync with the code. Rules are error (blocking) or warning (flagged, not blocking), since a governance process needs both.
- **`src/duplicate_detection.py`**: duplicate-identification reports built on normalized matching (case-folding, umlaut transliteration, legal-suffix stripping) rather than naive exact-string comparison, since real master-data duplicates are almost never identical strings. Two independent matching passes (normalized name plus postal code, and exact VAT ID) catch two different failure modes: a same-company-typed-differently duplicate, and a same-legal-entity-different-trading-name duplicate that name matching alone would miss.
- **`src/change_requests.py`**: routine data-maintenance requests and the audit trail. A `ChangeRequest` goes through an explicit SUBMITTED, VALIDATED, APPLIED (or REJECTED) state machine, validated against the business rules before touching the master dataset, with every transition producing an audit-trail entry (not reconstructed after the fact from the final data state, which would lose the "why"). Includes SLA breach detection (`check_sla`).
- **`src/reports.py`**: assembles the data-quality report a data steward pulls up before a governance meeting: violations and duplicates across all three object types in one place.
- **`src/seed_data.py`**: a small, deliberately messy starting dataset with known issues (a customer duplicated under a transliterated and re-capitalized name, a customer duplicated under a different trading name sharing one VAT ID, a material duplicated under two IDs, a vendor with out-of-range payment terms), so the reports have known findings to surface.

## Scope

The data is synthetic. The seed dataset is a small, hand-built set of placeholder companies and materials, and the workbench runs standalone without connecting to an ERP or SAP system. It implements the governance logic that sits on top of an ERP system: business-rule validation, duplicate detection, a change-request state machine, service-level tracking, and an audit trail, tested against deliberately messy data.

The domain model covers the core master-data fields. Production SAP master records carry many more fields and country-specific validation rules, and VAT ID format checking here uses one general pattern (2 letters plus at least 2 alphanumeric characters) rather than each EU country's specific format.

## Tests

52 tests (`pytest tests/ -v`), all passing, including:

- Business-rule tests for every rule (customer, vendor, material), covering both the positive case (rule does not fire on a clean record) and the negative case, plus a check that multiple violations on one record are all collected, not just the first.
- Duplicate-detection tests showing the normalization catches near-duplicates (umlaut transliteration, legal-suffix variance, capitalization) without false positives (two genuinely different companies, or two different records that both have no VAT ID, are not grouped together).
- Change-request lifecycle tests covering the full state machine, including that a request with a blocking violation is rejected and never touches the master dataset, that an UPDATE replaces rather than appends, and that CREATE/UPDATE correctly reject invalid preconditions (ID already exists or does not exist).
- Audit-trail tests confirming every state transition produces an entry, a rejected request's trail stops at "rejected" rather than showing a phantom "applied," and the returned log is a snapshot, not a live reference.
- Service-level tests: a request within SLA does not raise, one past SLA does, and a request that reached a terminal state (APPLIED or REJECTED) never breaches SLA regardless of age, since the SLA is about resolution time, not total lifespan.
- Report tests confirming clean records are excluded from the violations output (so the report stays readable), and that warning-only records are surfaced but not counted in the "records with errors" total.

## Project structure

```
src/
  records.py
  business_rules.py
  duplicate_detection.py
  change_requests.py
  reports.py
  seed_data.py
tests/
  test_business_rules.py
  test_duplicate_detection.py
  test_change_requests.py
  test_reports.py
run_demo.py
requirements.txt
pytest.ini
```

## Running it

```bash
pip install -r requirements.txt
python3 run_demo.py         # data quality report + change-request walkthrough + audit trail
pytest tests/ -v             # 52 tests
```

## Notes

**A fixture lesson from development.** The first version of the test suite used placeholder VAT IDs like `"DE1"` in fixtures unrelated to VAT-ID testing (for example testing that an UPDATE replaces rather than appends a record). These tripped the VAT-ID-format rule unintentionally, since `"DE1"` does not match the expected format. Five tests failed not because the governance logic was wrong but because the fixtures accidentally exercised a rule the tests were not about, which also confirmed the VAT-ID format rule works. I fixed it by using a valid-format VAT ID (`"DE123456789"`) throughout the change-request tests and reran the full suite (52/52 passing).

## Possible extensions

- Country-specific VAT ID format validation for each EU country.
- Importing records from an ERP export (CSV or IDoc-style files).
- A web or spreadsheet front end for the change-request queue.
