def normalize_contact(row):
    return {"id":row["id"],"email":row["email"],"tags":row.get("tags", "").split(";") if row.get("tags") else []}
