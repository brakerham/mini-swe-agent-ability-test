from .cursor import encode, decode

def page(connection, limit=50, cursor=None, kind=None):
    offset = 0 if cursor is None else decode(cursor, kind)[1]
    where, params = ("", []) if kind is None else (" WHERE kind = ?", [kind])
    rows = connection.execute("SELECT id,timestamp,kind,payload FROM events" + where + " ORDER BY timestamp LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
    items = [dict(zip(("id","timestamp","kind","payload"), row)) for row in rows]
    token = encode(items[-1]["timestamp"], offset + len(items), kind) if len(items) == limit else None
    return {"items":items,"next_cursor":token}
