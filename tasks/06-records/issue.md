# Support quoted CSV and predictable row-level validation

Repair `contactio.csvio.import_contacts(text)` and `export_contacts(contacts)`
plus `contactio.normalize.normalize_contact(row)`.
Input is CSV text. Read quoted commas, embedded newlines and a leading UTF-8
BOM correctly. Header names are stripped and lowercased. Exactly one id and
one email header are required; duplicate normalized headers, missing required
headers, empty input and invalid CSV quoting raise ValueError for the import.
Optional tags header; ignore other named columns. Empty physical lines outside
quoted fields are skipped; whitespace-only records are data. Ignore one leading
BOM only, so repeated BOMs do not silently change the header.

Normalize each row: id = stripped string (case-sensitive), email = stripped
lowercase string containing exactly one @ with nonempty local/domain parts
and no whitespace. Tags split by ';', strip, discard empty values, remove
duplicates in first-occurrence order. Missing tags means []. A missing/blank
id or invalid email raises ValueError from normalize_contact.

Return {"contacts": [normalized dicts], "errors": [{"row":N,"reason":S}]}.
Error reasons are "columns" for wrong field count, "id" for blank id,
"email" for invalid email, and "duplicate" for an id already successfully
imported. Apply that priority. Invalid rows do not reserve ids. Row numbers
count nonempty logical CSV records: header=1, first data record=2; embedded newlines
do not add a record. Preserve valid record order and continue after row
errors. Never mutate input dictionaries.

Export normalized dicts with columns id,email,tags, a header, LF line endings,
tags joined by ';', and proper CSV quoting. import(export(contacts)) roundtrips
valid normalized records including commas/newlines in id and tags.

## Submission scope

You may change exactly these implementation files:

- `src/contactio/normalize.py`
- `src/contactio/csvio.py`

You may also add or edit `tests/*.py` as evidence of your own verification.
The evaluator restores the original public tests before grading and runs
separate acceptance tests. Authored test changes cannot alter the score.
Keep all other files unchanged; do not create additional source modules.
