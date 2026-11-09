import base64
import json

def encode(timestamp, event_id, kind):
    return base64.urlsafe_b64encode(json.dumps({"v":1,"t":timestamp,"id":event_id,"kind":kind}).encode()).decode()

def decode(token, kind):
    data = json.loads(base64.urlsafe_b64decode(token))
    return data["t"], data["id"]
