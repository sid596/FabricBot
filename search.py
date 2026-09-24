"""Price catalogue resolution. Every call uses the current sheet snapshot."""
from sheets import get_catalogue


def catalogue_records():
    headers, rows = get_catalogue()
    records = []
    for row in rows:
        cells = dict(zip(headers, row))
        if not cells.get("Quality"):
            continue
        records.append({
            "brand": cells.get("t", ""),
            "album": cells.get("Album", ""),
            "quality": cells["Quality"],
            "cut rate": cells.get("Cut Rate", ""),
            "price": cells.get("Price", ""),
            "width": cells.get("Width", ""),
        })
    return records


def search_fabric(query):
    query = (query or "").strip().casefold()
    if not query:
        return []
    return [row for row in catalogue_records()
            if query in row["album"].casefold() or query in row["quality"].casefold()]
