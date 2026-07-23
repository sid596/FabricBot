from sheets import headers, rows
header_index = {}

for i, header in enumerate(headers):
    header_index[header] = i




def search_fabric(query):

    query = query.lower()

    results = []

    for row in rows:

        album = row[header_index["Album"]].lower()
        quality = row[header_index["Quality"]].lower()

        if query in album or query in quality:
            results.append({
                "album": row[header_index["Album"]],
                "quality": row[header_index["Quality"]],
                "cut rate": row[header_index["Cut Rate"]],
                "price": row[header_index["Price"]],
                "width": row[header_index["Width"]]
            })

    return results