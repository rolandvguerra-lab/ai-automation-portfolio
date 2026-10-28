"""Validate synthetic customer order records from a JSON file."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "customer_id": str,
    "name": str,
    "email": str,
    "order_total": (int, float),
    "status": str,
}
ALLOWED_STATUSES = {"pending", "paid", "shipped", "cancelled"}


def _is_finite_number(value: int | float) -> bool:
    """Return False for infinities, NaN, and integers outside float range."""
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_record(record: Any, index: int) -> list[str]:
    """Return readable validation errors for one record (1-based index)."""
    prefix = f"Record {index}"
    if not isinstance(record, dict):
        return [f"{prefix}: expected a JSON object, got {type(record).__name__}."]

    errors: list[str] = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in record:
            errors.append(f"{prefix}: missing required field '{field}'.")
            continue
        value = record[field]
        # bool subclasses int in Python, but is not a valid monetary amount.
        valid_type = (
            isinstance(value, (int, float)) and not isinstance(value, bool)
            if field == "order_total"
            else isinstance(value, expected_type)
        )
        if not valid_type:
            expected = "number" if field == "order_total" else expected_type.__name__
            errors.append(f"{prefix}: field '{field}' must be {expected}; got {type(value).__name__}.")

    customer_id = record.get("customer_id")
    if isinstance(customer_id, str) and not customer_id.strip():
        errors.append(f"{prefix}: field 'customer_id' must not be blank.")
    if isinstance(record.get("name"), str) and not record["name"].strip():
        errors.append(f"{prefix}: field 'name' must not be empty.")
    if isinstance(record.get("email"), str) and "@" not in record["email"]:
        errors.append(f"{prefix}: field 'email' must contain '@'.")

    total = record.get("order_total")
    if isinstance(total, (int, float)) and not isinstance(total, bool):
        if not _is_finite_number(total):
            errors.append(f"{prefix}: field 'order_total' must be finite.")
        elif total < 0:
            errors.append(f"{prefix}: field 'order_total' must be zero or greater.")

    status = record.get("status")
    if isinstance(status, str) and status not in ALLOWED_STATUSES:
        choices = ", ".join(sorted(ALLOWED_STATUSES))
        errors.append(f"{prefix}: field 'status' must be one of: {choices}.")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    """Validate a top-level JSON object containing a records array."""
    if not isinstance(payload, dict):
        return {"valid_records": [], "errors": ["Input must be a JSON object."]}
    records = payload.get("records")
    if not isinstance(records, list):
        return {"valid_records": [], "errors": ["Input field 'records' must be a JSON array."]}

    valid_records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_customer_ids: dict[str, int] = {}
    for index, record in enumerate(records, start=1):
        record_errors = validate_record(record, index)
        if isinstance(record, dict):
            customer_id = record.get("customer_id")
            if isinstance(customer_id, str) and customer_id.strip():
                normalized_id = customer_id.strip().casefold()
                first_index = seen_customer_ids.get(normalized_id)
                if first_index is not None:
                    record_errors.append(
                        f"Record {index}: field 'customer_id' duplicates record {first_index}."
                    )
                else:
                    seen_customer_ids[normalized_id] = index
        if record_errors:
            errors.extend(record_errors)
        else:
            valid_records.append(record)
    return {"valid_records": valid_records, "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate customer order records in a JSON file."
    )
    parser.add_argument("input", type=Path, help="path to an input JSON file")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="write report to a file (prints to terminal by default)",
    )
    args = parser.parse_args(argv)

    try:
        with args.input.open(encoding="utf-8") as input_file:
            payload = json.load(input_file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read valid JSON from '{args.input}': {exc}", file=sys.stderr)
        return 2

    report = validate_payload(payload)
    records = payload.get("records") if isinstance(payload, dict) else None
    report["summary"] = {
        "input_records": len(records) if isinstance(records, list) else 0,
        "valid_records": len(report["valid_records"]),
        "invalid_records": len({
            error.split(":", 1)[0]
            for error in report["errors"]
            if error.startswith("Record ")
        }),
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"Could not write report to '{args.output}': {exc}", file=sys.stderr)
            return 2
    else:
        sys.stdout.write(rendered)
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
