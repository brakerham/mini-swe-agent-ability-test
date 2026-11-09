# Event pages duplicate or skip equal-timestamp events

Repair `eventlog.store.page(connection, limit=50, cursor=None, kind=None)`.
The supplied sqlite3 connection has table events(id INTEGER PRIMARY KEY,
timestamp INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL).
Return {"items": [dict(id,timestamp,kind,payload), ...], "next_cursor": str|None}.
Order ascending by (timestamp, id). Limit is an int from 1 through 100,
rejecting bool and all other values with ValueError. Filter by exact kind
when non-None. Do not alter rows or the connection's row_factory.

Use keyset pagination: cursor records the last (timestamp,id) and the kind
filter. A later page includes only keys strictly greater than that tuple.
Inserts before that key must not duplicate old items. next_cursor is None
whenever no more matching rows exist, including exactly-full final pages.

`eventlog.cursor.encode(timestamp, event_id, kind)` returns an opaque string;
`decode(token, kind)` returns the tuple (timestamp,event_id). It must roundtrip
signed 64-bit integer timestamps (negative allowed) and positive signed
64-bit integer IDs. kind is None or a string of at most 128 Unicode characters
without surrogate code points. Both APIs reject other values. Reject bool,
malformed/oversized tokens (>2048 chars), missing or extra fields, wrong
types, unsupported version and mismatched kind with ValueError. The wire
format is URL-safe base64 UTF-8 JSON with exact keys v,t,id,kind and v=1.
Duplicate JSON object keys are invalid; standard base64 + and / are invalid.
A cursor is an opaque position token, not an authentication mechanism.

## Submission scope

You may change exactly these implementation files:

- `src/eventlog/cursor.py`
- `src/eventlog/store.py`

You may also add or edit `tests/*.py` as evidence of your own verification.
The evaluator restores the original public tests before grading and runs
separate acceptance tests. Authored test changes cannot alter the score.
Keep all other files unchanged; do not create additional source modules.
