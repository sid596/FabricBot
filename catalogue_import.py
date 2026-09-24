"""Resumable Nuhome photo import. Website identities must exactly join the price sheet.

    python catalogue_import.py --all
    python catalogue_import.py --collection abaca
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
import logging
from pathlib import Path
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from PIL import Image, ImageOps
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from search import catalogue_records
from visual_search import BASE_DIR, DEFAULT_DB, MODEL_NAME, encode, normalise, open_index, save_records

log = logging.getLogger(__name__)
ROOT = "https://www.nuhome.in"


def checked_url(url):
    url = urljoin(ROOT, url)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.nuhome.in", "nuhome.in"}:
        raise ValueError("Catalogue links must remain on nuhome.in")
    return url


class Website:
    def __init__(self, cache_dir, refresh=False):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Angie-FabricCatalogue/1.0"
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        )))

    def page(self, url):
        url = checked_url(url)
        target = self.cache_dir / (sha256(url.encode()).hexdigest() + ".html")
        if self.refresh or not target.exists():
            time.sleep(.15)
            response = self.session.get(url, timeout=(10, 45))
            response.raise_for_status()
            target.write_text(response.text)
        return BeautifulSoup(target.read_text(), "html.parser")


def parse_collections(soup):
    return {normalise(a.get_text(" ", strip=True)): checked_url(a["href"])
            for a in soup.select('#collection_filter_result a[href*="/collection-detail/"]')}


def parse_patterns(soup):
    return [(p.select_one(".product_title").get_text(" ", strip=True), checked_url(p["href"]))
            for p in soup.select("#tab-patterns .product_list_wrap a[href]")
            if p.select_one(".product_title")]


def discover_patterns(web, url):
    """Some coordinating fabrics appear only in the paginated SKU tab."""
    found, visited = [], set()
    page_url = url
    while page_url and page_url not in visited:
        if len(visited) >= 100:
            raise ValueError("Unexpected collection pagination; refusing an unbounded crawl")
        visited.add(page_url)
        soup = web.page(page_url)
        found.extend(parse_patterns(soup))
        for link in soup.select("#tab-skus .product_list_wrap a[href]"):
            title = link.select_one(".product_title")
            if title:
                found.append((title.get_text(" ", strip=True), checked_url(link["href"])))
        next_link = soup.select_one('#tab-skus a[rel="next"]')
        page_url = checked_url(next_link["href"]) if next_link else None
        if page_url and urlparse(page_url).path != urlparse(url).path:
            raise ValueError("Pagination left the current collection")
    return list(dict.fromkeys(found))


def parse_product(soup, price_record):
    metadata = {}
    for item in soup.select(".sku_detail_info_list > .sku_detail_info_item"):
        label, value = item.select_one(".sku_detail_info_label"), item.select_one(".sku_detail_info")
        if label and value:
            metadata[label.get_text(" ", strip=True).lower()] = value.get_text(" ", strip=True)
    category = metadata.get("category", "").lower()
    end_use = metadata.get("end use", "").lower()
    uses = []
    if "sheer" in category or "sheer" in end_use:
        uses.append("sheer")
    if "curtain" in end_use and "sheer" not in category:
        uses.append("main")
    if "upholstery" in end_use:
        uses.append("upholstery")
    # 'Multipurpose' is not evidence for sheer use.
    if "multipurpose" in end_use:
        uses.extend(["main", "upholstery"])
    records = []
    for a in soup.select(".sku_colors_list a[href]"):
        image = a.select_one("img[src]")
        if not image:
            continue
        source = checked_url(a["href"])
        sku = urlparse(source).path.rstrip("/").split("/")[-1]
        records.append({
            "id": "nuhome-" + sha256(source.encode()).hexdigest()[:24],
            **{key: price_record[key] for key in ("brand", "album", "quality")},
            "sku": sku, "source_url": source, "image_url": checked_url(image["src"]),
            "uses": sorted(set(uses)), "composition": metadata.get("composition", ""),
            "category": metadata.get("category", ""), "design": metadata.get("design type", ""),
        })
    if not records:
        raise ValueError("No colour variants found; website structure may have changed")
    return records


def download_photo(record, image_dir, refresh=False):
    path = image_dir / f"{record['id']}.jpg"
    if refresh or not path.exists():
        response = requests.get(checked_url(record["image_url"]), timeout=(10, 45))
        response.raise_for_status()
        with Image.open(BytesIO(response.content)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((1024, 1024))
            temporary = path.with_suffix(".tmp")
            image.save(temporary, format="JPEG", quality=92)
            temporary.replace(path)
    return {**record, "image_path": str(path.resolve())}


def run_import(collections=None, db_path=DEFAULT_DB, refresh=False):
    db_path = Path(db_path)
    data_dir = db_path.parent
    images = data_dir / "photos"
    images.mkdir(parents=True, exist_ok=True)
    web = Website(data_dir / "web-cache", refresh=refresh)
    source_collections = parse_collections(web.page(ROOT + "/collections"))
    if not source_collections:
        raise ValueError("No collections found; website structure may have changed")
    prices = [p for p in catalogue_records() if normalise(p["brand"]) == "nuhome"]
    selected = {normalise(x) for x in collections} if collections else None
    prices = [p for p in prices if selected is None or normalise(p["album"]) in selected]
    by_album = {}
    for price in prices:
        by_album.setdefault(normalise(price["album"]), []).append(price)
    report = {"indexed": 0, "existing": 0, "unmatched_collections": [], "unmatched_qualities": [], "errors": []}
    db = open_index(db_path)
    existing = {row[0] for row in db.execute("SELECT id FROM fabrics WHERE model=?", (MODEL_NAME,))}
    try:
        for album, price_rows in by_album.items():
            url = source_collections.get(album)
            if not url:
                report["unmatched_collections"].append(price_rows[0]["album"])
                continue
            try:
                patterns = discover_patterns(web, url)
                if not patterns:
                    raise ValueError("No pattern links found")
            except Exception as exc:
                report["errors"].append({"url": url, "error": type(exc).__name__ + ": " + str(exc)})
                continue
            for price in price_rows:
                quality = normalise(price["quality"].removeprefix("Nuhome ").removeprefix("NuHome "))
                urls = [link for name, link in patterns if normalise(name) == quality]
                # Multiple colour URLs are fine; multiple product identities
                # with the same name need review instead of a guessed join.
                identities = {link.rsplit("/", 1)[0] for link in urls}
                if len(identities) != 1:
                    report["unmatched_qualities"].append({"album": price["album"], "quality": price["quality"]})
                    continue
                try:
                    records = None
                    for product_url in urls:
                        try:
                            records = parse_product(web.page(product_url), price)
                            break
                        except requests.HTTPError as exc:
                            if exc.response.status_code != 404:
                                raise
                    if records is None:
                        raise ValueError("All observed product links returned 404")
                    todo = [r for r in records if refresh or r["id"] not in existing or not (images / f"{r['id']}.jpg").exists()]
                    report["existing"] += len(records) - len(todo)
                    downloaded = []
                    # Bounded concurrent photo reads; failures remain retryable.
                    with ThreadPoolExecutor(max_workers=3) as pool:
                        futures = [(r, pool.submit(download_photo, r, images, refresh)) for r in todo]
                        for record, future in futures:
                            try:
                                downloaded.append(future.result())
                            except Exception as exc:
                                report["errors"].append({"url": record["image_url"], "error": type(exc).__name__})
                    for start in range(0, len(downloaded), 24):
                        batch = downloaded[start:start + 24]
                        photos = []
                        for record in batch:
                            with Image.open(record["image_path"]) as image:
                                photos.append(image.convert("RGB"))
                        vectors = encode(photos)
                        save_records(db, batch, vectors)
                        existing.update(r["id"] for r in batch)
                        report["indexed"] += len(batch)
                    log.info("%s / %s: %s variants (%s indexed total)", price["album"], price["quality"], len(records), report["indexed"])
                except Exception as exc:
                    log.exception("Could not index %s", price["quality"])
                    report["errors"].append({"url": urls[0], "error": type(exc).__name__ + ": " + str(exc)})
            (data_dir / "import-report.json").write_text(json.dumps(report, indent=2))
    finally:
        db.close()
    (data_dir / "import-report.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true")
    scope.add_argument("--collection", action="append")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--refresh", action="store_true", help="Re-read website metadata and recompute embeddings")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    report = run_import(args.collection, args.db, args.refresh)
    print(json.dumps(report, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
