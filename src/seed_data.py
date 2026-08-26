"""
seed_data.py
------------
A small, hand-built (not randomly generated) starting MasterDataset with
deliberately realistic messiness: near-duplicate customers/vendors
(same company, different spelling/capitalization/legal-suffix), one
material genuinely reused under two IDs, and otherwise-clean records —
so the duplicate-detection and validation reports have real, known
findings to surface, not a synthetically-perfect dataset.

NOT real company data — every name below is a placeholder invented for
this project.
"""

from datetime import date

from .records import CustomerRecord, VendorRecord, MaterialRecord, MasterDataset, RecordStatus


def build_seed_dataset() -> MasterDataset:
    customers = [
        CustomerRecord("CUST-1001", "Müller GmbH", "DE", "DE111222333", "Hauptstr. 1", "München", "80331", created_on=date(2021, 3, 15)),
        # Near-duplicate of CUST-1001: umlaut transliterated, different capitalization, no legal suffix in the name.
        CustomerRecord("CUST-1044", "MUELLER", "DE", None, "Hauptstrasse 1", "München", "80331", created_on=date(2023, 7, 2)),
        CustomerRecord("CUST-1002", "Nordwind Logistik AG", "DE", "DE444555666", "Speicherstr. 12", "Hamburg", "20457", created_on=date(2020, 1, 10)),
        CustomerRecord("CUST-1003", "Alpine Components S.A.", "FR", "FR12345678901", "Rue de Lyon 8", "Lyon", "69001", created_on=date(2022, 5, 20)),
        # Same VAT ID as CUST-1003 under a different trading name — the VAT-based dedup pass should catch this one.
        CustomerRecord("CUST-1099", "Alpine Components (Export Division)", "FR", "FR12345678901", "Rue de Lyon 8", "Lyon", "69001", created_on=date(2024, 2, 1)),
        CustomerRecord("CUST-1004", "Baltic Freight Ltd", "IN", "IN99887766", "MG Road 45", "Bengaluru", "560001", created_on=date(2023, 11, 3)),
    ]

    vendors = [
        VendorRecord("VEND-2001", "Stahlwerk Nord GmbH", "DE", "DE777888999", "Industriering 3", "Essen", "45127", 30, created_on=date(2019, 6, 1)),
        VendorRecord("VEND-2002", "Comptoir Industriel SARL", "FR", "FR22334455667", "Zone Industrielle 5", "Lille", "59000", 45, created_on=date(2021, 9, 12)),
        # Payment terms flagged by the warning rule (out of the typical 0-120 day range).
        VendorRecord("VEND-2003", "Precision Parts Ltd", "GB", None, "Unit 4 Trade Park", "Manchester", "M1 2AB", 180, created_on=date(2022, 3, 8)),
        VendorRecord("VEND-2004", "Nordic Components AB", "SE", "SE998877665", "Verkstadsgatan 9", "Göteborg", "41103", 30, created_on=date(2020, 11, 22)),
    ]

    materials = [
        MaterialRecord("MAT-3001", "Bolt M6x20 Steel", "RAW-METAL", "EA", 0.08, created_on=date(2018, 1, 1)),
        # Genuine duplicate: same description/group/UoM under a different ID (likely created independently by two plants).
        MaterialRecord("MAT-3087", "Bolt M6x20 Steel", "RAW-METAL", "EA", 0.09, created_on=date(2023, 4, 17)),
        MaterialRecord("MAT-3002", "Cardboard Box 30x30x30", "PACK-MAT", "EA", 0.45, created_on=date(2019, 8, 5)),
        MaterialRecord("MAT-3003", "Industrial Lubricant", "CHEM", "L", 12.50, created_on=date(2020, 2, 14)),
        # Blocked record: mid-transition, e.g. a material under a compliance/quality hold.
        MaterialRecord("MAT-3004", "Legacy Adhesive Compound X", "CHEM", "L", 8.10, status=RecordStatus.BLOCKED, created_on=date(2017, 5, 30)),
    ]

    return MasterDataset(customers=customers, vendors=vendors, materials=materials)
