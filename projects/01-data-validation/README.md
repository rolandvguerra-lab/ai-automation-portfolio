# Project 1 — Data validation

A small Python command-line portfolio demonstration that validates synthetic customer order records in JSON. It separates accepted records from rejected records and explains validation failures with record-specific messages.

## What it demonstrates

- Reading and writing JSON with Python's standard library
- Required-field and data-type checks
- Business rules for customer IDs, names, basic email formatting, finite non-negative totals, and allowed order statuses
- Clear validation messages and process exit codes for automated workflows
- Automated tests with `unittest`, including malformed input and file-handling failures

All names, email addresses, IDs, and orders here are fictional. The `.test` email domain is reserved for testing.

## Requirements

- Python 3.10 or newer
- No third-party packages

## Run the examples

From this project folder:

```powershell
python validate_records.py samples/valid_records.json
python validate_records.py samples/invalid_records.json
```

The valid sample exits with code `0`. The invalid sample exits with code `1` after reporting validation errors. The input must be a JSON object containing a `records` array.

To save the report to a file:

```powershell
python validate_records.py samples/invalid_records.json --output report.json
```

A record with any validation error is excluded from `valid_records`. The generated report contains `valid_records`, an `errors` list, and summary counts. A saved example is available at `samples/invalid_report.json`.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The input was read and every record passed validation. |
| `1` | The input was read, but one or more records failed validation. |
| `2` | The input file could not be read or parsed, the report could not be written, or the required input argument was omitted. |

## Data rules

| Field | Type | Rule |
| --- | --- | --- |
| `customer_id` | string | Required; cannot be blank; unique after trimming whitespace and ignoring case |
| `name` | string | Required; cannot be blank |
| `email` | string | Required; must contain `@` |
| `order_total` | number | Required; finite and zero or greater; booleans are rejected |
| `status` | string | Required; `pending`, `paid`, `shipped`, or `cancelled` |

## Sample results and test coverage

The latest verified test run passed all **15 tests**:

```text
python -m unittest discover -s tests -v
Ran 15 tests
OK
```

The valid sample accepts both records and exits with code `0`:

```json
{
  "input_records": 2,
  "valid_records": 2,
  "invalid_records": 0
}
```

The invalid sample rejects both records and exits with code `1`. Its report includes errors such as:

```text
Record 1: field 'email' must contain '@'.
Record 1: field 'order_total' must be zero or greater.
Record 1: field 'status' must be one of: cancelled, paid, pending, shipped.
Record 2: field 'order_total' must be number; got str.
```

A generated JSON report excerpt:

```json
{
  "valid_records": [],
  "errors": [
    "Record 1: field 'email' must contain '@'.",
    "Record 1: field 'order_total' must be zero or greater."
  ],
  "summary": {
    "input_records": 2,
    "valid_records": 0,
    "invalid_records": 2
  }
}
```

The tests cover valid and invalid records, missing fields, invalid top-level structures, non-object records, NaN and infinite amounts, duplicate IDs, missing input files, malformed JSON, report-writing failures, and JSON report output.

## Project status and limitations

This is a portfolio demonstration of basic Python validation and JSON reporting, not a production customer-data system. It checks required fields and types, blank names and IDs, duplicate customer IDs (case-insensitive after trimming), a basic email check, finite non-negative totals, and an allowed status list. The email rule only checks for `@`; it does not fully validate an address. Status values are case-sensitive, monetary values use Python numbers rather than currency-safe decimal arithmetic, and the tool reads the full input file into memory.

Possible future improvements include stricter email validation, currency-aware decimal handling, configurable validation rules, and streaming support for larger files.

## Run the tests

```powershell
python -m unittest discover -s tests -v
```

## Demo Results

### Automated Tests — 15 Passed
![Automated test results](images/Automated%20tests.png)

### Valid JSON Input
![Valid input results](images/Valid%20input.png)

### Invalid JSON Input
![Invalid input results](images/invalid%20input.png)
