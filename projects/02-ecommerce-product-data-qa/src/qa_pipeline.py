"""Conservative ecommerce catalog QA for the fictional portfolio sample."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "products_source.csv"
OUT = ROOT / "output"
FIELDS = ["product_id", "sku", "product_name", "category", "unit_price", "currency", "quantity", "status"]


def read_source(path: Path = SOURCE) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"Expected columns {FIELDS}, got {reader.fieldnames}")
        return [dict(row) for row in reader]


def parse_price(raw: str, currency: str) -> tuple[str | None, str | None]:
    """Parse only plain decimals and conventional 1,234.56 grouping."""
    value = raw.strip()
    if not value:
        return None, "PRICE_MISSING"
    if value.startswith("$"):
        if currency.upper() != "USD":
            return None, "PRICE_CURRENCY_CONFLICT"
        value = value[1:].strip()
    # Commas are accepted only in correctly grouped thousands, with dot decimals.
    if "," in value:
        if not re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", value):
            return None, "PRICE_AMBIGUOUS_FORMAT"
        value = value.replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", value):
        return None, "PRICE_INVALID_FORMAT"
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None, "PRICE_INVALID_FORMAT"
    if amount <= 0:
        return None, "PRICE_NONPOSITIVE"
    return f"{amount:.2f}", None


def validate_rows(source_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    cleaned = []
    issues = []
    skus: dict[str, list[int]] = defaultdict(list)
    normalized = []

    for source_row, original in enumerate(source_rows, start=2):  # header is source row 1
        row = {key: (value or "").strip() for key, value in original.items()}
        row["sku"] = row["sku"].upper()
        row["currency"] = row["currency"].upper()
        row["status"] = row["status"].lower()
        normalized.append((source_row, row, original))
        if row["sku"]:
            skus[row["sku"]].append(source_row)

    duplicate_skus = {sku for sku, rows in skus.items() if len(rows) > 1}
    for source_row, row, original in normalized:
        row_issues: list[tuple[str, str, str, str, str]] = []

        def add(field: str, code: str, severity: str, action: str, note: str) -> None:
            row_issues.append((field, code, severity, action, note))

        if not row["sku"]:
            add("sku", "SKU_MISSING", "review", "left blank", "A unique SKU cannot be inferred.")
        elif row["sku"] in duplicate_skus:
            add("sku", "SKU_DUPLICATE", "review", "retained; no row removed", "Confirm the intended product identity and SKU assignment.")

        name = row["product_name"]
        if not name or name in {"?", "*", "-", "N/A", "NA"}:
            add("product_name", "PRODUCT_NAME_MISSING", "review", "retained as supplied", "Name is blank or a placeholder; source data is required.")
        if not row["category"]:
            add("category", "CATEGORY_MISSING", "review", "left blank", "Category cannot be safely inferred from the product name.")

        price, price_error = parse_price(row["unit_price"], row["currency"])
        if price_error:
            add("unit_price", price_error, "review", "retained as supplied", "Price was not changed because it is invalid or ambiguous.")
        else:
            row["unit_price"] = price or row["unit_price"]

        quantity = row["quantity"]
        if not quantity:
            add("quantity", "QUANTITY_MISSING", "review", "left blank", "Quantity cannot be inferred.")
        elif not re.fullmatch(r"-?\d+", quantity):
            add("quantity", "QUANTITY_INVALID_FORMAT", "review", "retained as supplied", "Quantity must be a whole number; no rounding or parsing guess was applied.")
        elif int(quantity) < 0:
            add("quantity", "QUANTITY_NEGATIVE", "review", "retained as supplied", "Confirm whether the source value is a correction or an error.")
        else:
            row["quantity"] = str(int(quantity))

        if row["currency"] and row["currency"] != "USD":
            add("currency", "CURRENCY_UNSUPPORTED", "review", "retained as supplied", "This demo validates USD only; confirm currency before conversion or use.")

        row["qa_status"] = "needs_review" if row_issues else "ready_for_review"
        row["issue_codes"] = "|".join(issue[1] for issue in row_issues)
        cleaned.append(row)
        for field, code, severity, action, note in row_issues:
            issues.append({
                "source_row": str(source_row),
                "product_id": row["product_id"],
                "sku": row["sku"],
                "field": field,
                "issue_code": code,
                "severity": severity,
                "source_value": original.get(field, ""),
                "action_taken": action,
                "review_note": note,
            })
    return cleaned, issues


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(source_path: Path = SOURCE, output_dir: Path = OUT) -> dict[str, int]:
    source_rows = read_source(source_path)
    cleaned, issues = validate_rows(source_rows)
    write_csv(output_dir / "products_cleaned_working.csv", cleaned, FIELDS + ["qa_status", "issue_codes"])
    issue_fields = ["source_row", "product_id", "sku", "field", "issue_code", "severity", "source_value", "action_taken", "review_note"]
    write_csv(output_dir / "exceptions_issue_log.csv", issues, issue_fields)
    counts = Counter(issue["issue_code"] for issue in issues)
    return {"records": len(source_rows), "rows_needing_review": sum(row["qa_status"] == "needs_review" for row in cleaned), "issue_instances": len(issues), **dict(counts)}


if __name__ == "__main__":
    summary = run()
    for key, value in summary.items():
        print(f"{key}: {value}")
