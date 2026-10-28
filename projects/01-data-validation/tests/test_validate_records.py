"""Automated tests for the customer order validation demo."""
import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from validate_records import main, validate_payload, validate_record


class ValidateRecordTests(unittest.TestCase):
    def setUp(self):
        self.valid_record = {
            "customer_id": "CUST-1001",
            "name": "Avery Sample",
            "email": "avery@example.test",
            "order_total": 125.50,
            "status": "paid",
        }

    def test_accepts_valid_record(self):
        self.assertEqual(validate_record(self.valid_record, 1), [])

    def test_reports_missing_fields_and_invalid_values(self):
        record = {
            "customer_id": "CUST-1002",
            "email": "not-an-email",
            "order_total": -4,
            "status": "lost",
        }
        errors = validate_record(record, 2)
        self.assertTrue(any("missing required field 'name'" in error for error in errors))
        self.assertTrue(any("must contain '@'" in error for error in errors))
        self.assertTrue(any("zero or greater" in error for error in errors))
        self.assertTrue(any("must be one of" in error for error in errors))

    def test_rejects_blank_customer_id_and_name(self):
        record = {**self.valid_record, "customer_id": "  ", "name": " "}
        errors = validate_record(record, 1)
        self.assertTrue(any("customer_id' must not be blank" in error for error in errors))
        self.assertTrue(any("name' must not be empty" in error for error in errors))

    def test_rejects_boolean_as_order_total(self):
        record = {**self.valid_record, "order_total": True}
        self.assertTrue(any("field 'order_total' must be number" in error
                            for error in validate_record(record, 1)))

    def test_rejects_nan_and_infinite_order_totals(self):
        for total in (math.nan, math.inf, -math.inf, 10**400):
            with self.subTest(total=repr(total)):
                record = {**self.valid_record, "order_total": total}
                errors = validate_record(record, 1)
                self.assertTrue(any("order_total' must be finite" in error for error in errors))

    def test_rejects_non_object_record(self):
        errors = validate_record(["not", "an", "object"], 3)
        self.assertEqual(errors, ["Record 3: expected a JSON object, got list."])


class ValidatePayloadTests(unittest.TestCase):
    def setUp(self):
        self.valid_record = {
            "customer_id": "CUST-1001",
            "name": "Avery Sample",
            "email": "avery@example.test",
            "order_total": 125.50,
            "status": "paid",
        }

    def test_keeps_valid_records_and_reports_invalid_ones(self):
        report = validate_payload({"records": [self.valid_record, {"customer_id": 9}]})
        self.assertEqual(report["valid_records"], [self.valid_record])
        self.assertTrue(report["errors"])

    def test_rejects_invalid_top_level_structures(self):
        cases = (
            ([], "Input must be a JSON object."),
            ({}, "Input field 'records' must be a JSON array."),
            ({"records": "not an array"}, "Input field 'records' must be a JSON array."),
        )
        for payload, expected_error in cases:
            with self.subTest(payload=payload):
                report = validate_payload(payload)
                self.assertEqual(report["errors"], [expected_error])

    def test_rejects_non_object_record_inside_array(self):
        report = validate_payload({"records": [self.valid_record, "bad record"]})
        self.assertEqual(report["valid_records"], [self.valid_record])
        self.assertIn("Record 2: expected a JSON object, got str.", report["errors"])

    def test_rejects_duplicate_customer_ids_case_insensitively(self):
        duplicate = {**self.valid_record, "customer_id": " cust-1001 "}
        report = validate_payload({"records": [self.valid_record, duplicate]})
        self.assertEqual(report["valid_records"], [self.valid_record])
        self.assertIn("Record 2: field 'customer_id' duplicates record 1.", report["errors"])


class CliTests(unittest.TestCase):
    def _temporary_directory(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).parent)

    def test_cli_writes_json_report_and_returns_failure_for_bad_records(self):
        with self._temporary_directory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "report.json"
            source.write_text(json.dumps({"records": [{"customer_id": 4}]}), encoding="utf-8")
            result = main([str(source), "--output", str(output)])
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result, 1)
        self.assertEqual(report["summary"]["input_records"], 1)
        self.assertEqual(report["summary"]["valid_records"], 0)
        self.assertEqual(report["summary"]["invalid_records"], 1)

    def test_cli_reports_missing_input_file(self):
        with self._temporary_directory() as directory:
            missing = Path(directory) / "missing.json"
            stderr = StringIO()
            with redirect_stderr(stderr):
                result = main([str(missing)])
        self.assertEqual(result, 2)
        self.assertIn("Could not read valid JSON", stderr.getvalue())
        self.assertIn(str(missing), stderr.getvalue())

    def test_cli_reports_malformed_json(self):
        with self._temporary_directory() as directory:
            source = Path(directory) / "malformed.json"
            source.write_text('{"records": [}', encoding="utf-8")
            stderr = StringIO()
            with redirect_stderr(stderr):
                result = main([str(source)])
        self.assertEqual(result, 2)
        self.assertIn("Could not read valid JSON", stderr.getvalue())

    def test_cli_rejects_nan_in_json_order_total(self):
        with self._temporary_directory() as directory:
            source = Path(directory) / "nan.json"
            source.write_text(
                '{"records": [{"customer_id":"C-1","name":"A","email":"a@b.test","order_total":NaN,"status":"paid"}]}',
                encoding="utf-8",
            )
            output = Path(directory) / "report.json"
            result = main([str(source), "--output", str(output)])
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result, 1)
        self.assertTrue(any("order_total' must be finite" in error for error in report["errors"]))

    def test_cli_reports_output_write_failure(self):
        with self._temporary_directory() as directory:
            source = Path(directory) / "input.json"
            source.write_text('{"records": []}', encoding="utf-8")
            stderr = StringIO()
            with patch.object(Path, "write_text", side_effect=OSError("disk full")):
                with redirect_stderr(stderr):
                    result = main([str(source), "--output", str(Path(directory) / "report.json")])
        self.assertEqual(result, 2)
        self.assertIn("Could not write report", stderr.getvalue())
        self.assertIn("disk full", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
