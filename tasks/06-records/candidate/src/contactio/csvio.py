from .normalize import normalize_contact

def import_contacts(text):
    lines = text.splitlines()
    fields = lines[0].split(",")
    return {"contacts":[normalize_contact(dict(zip(fields,line.split(",")))) for line in lines[1:] if line], "errors":[]}

def export_contacts(contacts):
    return "id,email,tags\n" + "".join(f"{row['id']},{row['email']},{';'.join(row['tags'])}\n" for row in contacts)
