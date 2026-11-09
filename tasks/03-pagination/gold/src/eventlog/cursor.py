import base64
import binascii
import json
import re

def _valid_kind(kind):
    return kind is None or (isinstance(kind, str) and len(kind) <= 128 and
                            all(not 0xD800 <= ord(char) <= 0xDFFF for char in kind))

def _valid(timestamp, event_id, kind):
    return (type(timestamp) is int and -(2**63) <= timestamp < 2**63 and
            type(event_id) is int and 0 < event_id < 2**63 and _valid_kind(kind))

def encode(timestamp, event_id, kind):
    if not _valid(timestamp, event_id, kind):
        raise ValueError("invalid cursor values")
    raw = json.dumps({"v":1,"t":timestamp,"id":event_id,"kind":kind}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()

def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate cursor field")
        result[key] = value
    return result

def decode(token, kind):
    if not isinstance(token, str) or not token or len(token) > 2048 or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", token):
        raise ValueError("invalid cursor")
    try:
        raw = base64.b64decode(token.encode("ascii"), altchars=b"-_", validate=True)
        data = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise ValueError("invalid cursor") from exc
    if not isinstance(data, dict) or set(data) != {"v","t","id","kind"}:
        raise ValueError("invalid cursor fields")
    if type(data["v"]) is not int or data["v"] != 1 or not _valid(data["t"], data["id"], data["kind"]) or data["kind"] != kind:
        raise ValueError("invalid cursor values or filter")
    return data["t"], data["id"]
