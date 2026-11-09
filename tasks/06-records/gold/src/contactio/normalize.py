def normalize_contact(row):
    identifier = row.get("id", "").strip()
    if not identifier:
        raise ValueError("id")
    email = row.get("email", "").strip().lower()
    parts = email.split("@")
    if len(parts) != 2 or not all(parts) or any(char.isspace() for char in email):
        raise ValueError("email")
    tags = list(dict.fromkeys(tag.strip() for tag in row.get("tags", "").split(";") if tag.strip()))
    return {"id":identifier,"email":email,"tags":tags}
