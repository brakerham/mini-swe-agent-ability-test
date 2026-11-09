from .cursor import encode, decode, _valid_kind

def page(connection, limit=50, cursor=None, kind=None):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be in [1, 100]")
    if not _valid_kind(kind):
        raise ValueError("invalid kind")
    clauses, params = [], []
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)
    if cursor is not None:
        timestamp, event_id = decode(cursor, kind)
        clauses.append("(timestamp > ? OR (timestamp = ? AND id > ?))")
        params.extend([timestamp, timestamp, event_id])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = connection.execute("SELECT id,timestamp,kind,payload FROM events" + where + " ORDER BY timestamp, id LIMIT ?", params + [limit + 1]).fetchall()
    items = [dict(zip(("id","timestamp","kind","payload"), row)) for row in rows[:limit]]
    token = encode(items[-1]["timestamp"], items[-1]["id"], kind) if len(rows) > limit else None
    return {"items":items,"next_cursor":token}
