import csv
import io
from .normalize import normalize_contact

def import_contacts(text):
    reader = csv.reader(io.StringIO(text.removeprefix("\ufeff"), newline=""), strict=True)
    try:
        headers = next(reader)
        headers = [name.strip().lower() for name in headers]
        if len(set(headers)) != len(headers) or not {"id","email"}.issubset(headers):
            raise ValueError("invalid headers")
        contacts, errors, seen = [], [], set()
        record = 1
        for values in reader:
            if not values:
                continue
            record += 1
            if len(values) != len(headers):
                errors.append({"row":record,"reason":"columns"})
                continue
            try:
                contact = normalize_contact(dict(zip(headers,values)))
            except ValueError as exc:
                errors.append({"row":record,"reason":str(exc)})
                continue
            if contact["id"] in seen:
                errors.append({"row":record,"reason":"duplicate"})
                continue
            seen.add(contact["id"])
            contacts.append(contact)
        return {"contacts":contacts,"errors":errors}
    except (csv.Error, StopIteration) as exc:
        raise ValueError("invalid CSV") from exc

def export_contacts(contacts):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["id","email","tags"])
    for row in contacts:
        writer.writerow([row["id"],row["email"],";".join(row["tags"])])
    return output.getvalue()
