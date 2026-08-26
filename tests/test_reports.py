from src.seed_data import build_seed_dataset
from src.reports import run_data_quality_report
from src.records import MasterDataset, CustomerRecord


class TestDataQualityReport:
    def test_seed_dataset_produces_a_report_with_known_findings(self):
        dataset = build_seed_dataset()
        report = run_data_quality_report(dataset)
        # The seed dataset is deliberately built with known issues —
        # a report finding NOTHING would indicate a bug, not a clean dataset.
        assert report.total_duplicate_groups > 0

    def test_clean_dataset_produces_zero_violations_and_zero_duplicates(self):
        dataset = MasterDataset(
            customers=[CustomerRecord("C1", "Acme GmbH", "DE", "DE123456789", "Str 1", "Berlin", "10115")]
        )
        report = run_data_quality_report(dataset)
        assert report.customer_violations == {}
        assert report.total_duplicate_groups == 0

    def test_clean_records_are_excluded_from_the_violations_dict(self):
        # A record with zero violations should not appear as a key with
        # an empty list — the report should only surface records that
        # actually need attention.
        dataset = MasterDataset(
            customers=[
                CustomerRecord("C1", "Acme GmbH", "DE", "DE123456789", "Str 1", "Berlin", "10115"),  # clean
                CustomerRecord("C2", "Bad Co", "ZZ", None, "Str 2", "Berlin", "10115"),  # has violations
            ]
        )
        report = run_data_quality_report(dataset)
        assert "C1" not in report.customer_violations
        assert "C2" in report.customer_violations

    def test_total_records_with_errors_only_counts_error_severity_not_warnings(self):
        from src.records import VendorRecord
        dataset = MasterDataset(
            vendors=[
                # Warning-only vendor (payment terms out of range) — should NOT count as "with errors".
                VendorRecord("V1", "Warn Co", "DE", "DE123456789", "Str", "Berlin", "10115", 200),
            ]
        )
        report = run_data_quality_report(dataset)
        assert report.total_records_with_errors == 0
        assert len(report.vendor_violations) == 1  # still surfaced, just not counted as an "error" record
