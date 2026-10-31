import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from src.qa_pipeline import FIELDS, SOURCE, parse_price, read_source, run, validate_rows


class PriceParsingTests(unittest.TestCase):
    def test_plain_and_us_grouped_prices_are_standardized(self):
        self.assertEqual(parse_price("18", "USD"), ("18.00", None))
        self.assertEqual(parse_price("1,299.00", "USD"), ("1299.00", None))
        self.assertEqual(parse_price("$24.5", "USD"), ("24.50", None))

    def test_ambiguous_and_nonpositive_prices_are_flagged(self):
        self.assertEqual(parse_price("12,99", "USD")[1], "PRICE_AMBIGUOUS_FORMAT")
        self.assertEqual(parse_price("-6.00", "USD")[1], "PRICE_NONPOSITIVE")
        self.assertEqual(parse_price("0.00", "USD")[1], "PRICE_NONPOSITIVE")


class PipelineTests(unittest.TestCase):
    def test_source_file_is_preserved_and_outputs_are_created(self):
        before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            stats = run(SOURCE, Path(temp))
            self.assertTrue((Path(temp) / "products_cleaned_working.csv").exists())
            self.assertTrue((Path(temp) / "exceptions_issue_log.csv").exists())
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), before)
        self.assertEqual(stats["records"], 35)

    def test_duplicate_sku_flags_both_rows_without_deduplication(self):
        cleaned, _ = validate_rows(read_source())
        matches = [row for row in cleaned if row["sku"] == "ECO-006"]
        self.assertEqual(len(matches), 2)
        self.assertTrue(all("SKU_DUPLICATE" in row["issue_codes"] for row in matches))

    def test_ambiguous_price_and_missing_business_fields_remain_unfilled(self):
        cleaned, issues = validate_rows(read_source())
        row = next(item for item in cleaned if item["product_id"] == "P-1030")
        self.assertEqual(row["unit_price"], "12,99")
        self.assertEqual(row["product_name"], "Bamboo Toothbrush Set")
        missing_name = next(item for item in cleaned if item["product_id"] == "P-1028")
        self.assertEqual(missing_name["product_name"], "?")
        self.assertIn("PRICE_AMBIGUOUS_FORMAT", {item["issue_code"] for item in issues})

    def test_safe_whitespace_and_case_standardization_is_applied(self):
        cleaned, _ = validate_rows(read_source())
        row = next(item for item in cleaned if item["product_id"] == "P-1035")
        self.assertEqual(row["sku"], "ECO-035")
        self.assertEqual(row["category"], "Accessories")
        self.assertEqual(row["quantity"], "9")

    def test_negative_quantity_is_flagged_for_owner_review(self):
        _, issues = validate_rows(read_source())
        self.assertIn("QUANTITY_NEGATIVE", {item["issue_code"] for item in issues})


if __name__ == "__main__":
    unittest.main(verbosity=2)
