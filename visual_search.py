"""Local CLIP photo/text retrieval, joined to current Google Sheet prices."""
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from contextlib import closing

import numpy as np
from PIL import Image, ImageOps

from fabric_attributes import FabricPreferences
from search import catalogue_records

BASE_DIR = Path(__file__).resolve().parent
MODEL_NAME = "sentence-transformers/clip-ViT-B-32"
MODEL_REVISION = "327ab6726d33c0e22f920c83f2ff9e4bd38ca37f"
DEFAULT_DB = BASE_DIR / "data" / "fabrics.sqlite3"
_model = None
_model_lock = threading.Lock()


class CatalogueNotReady(RuntimeError):
    pass


def normalise(value):
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def record_key(record):
    return tuple(normalise(record.get(k, "")) for k in ("brand", "album", "quality"))


def encode(inputs):
    global _model
    with _model_lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise CatalogueNotReady("Visual search dependencies are not installed") from exc
            _model = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION)
        return np.asarray(_model.encode(inputs, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)


def open_index(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute('''CREATE TABLE IF NOT EXISTS fabrics (
        id TEXT PRIMARY KEY, record TEXT NOT NULL, embedding BLOB NOT NULL,
        model TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    return db


def save_records(db, records, vectors):
    with db:
        db.executemany("""INSERT INTO fabrics(id,record,embedding,model) VALUES(?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET record=excluded.record,
            embedding=excluded.embedding,model=excluded.model,updated_at=CURRENT_TIMESTAMP""",
            [(r["id"], json.dumps(r), np.asarray(v, dtype=np.float32).tobytes(), MODEL_NAME)
             for r, v in zip(records, vectors)])


def visual_query(preferences):
    parts = [preferences.description, *preferences.colours, *preferences.textures, *preferences.patterns]
    # Related shades broaden retrieval without losing the user's original shade.
    colour_words = " ".join(preferences.colours).lower()
    if any(c in colour_words for c in ("sage", "teal", "sea green")):
        parts.append("green blue-green sea green")
    return "A close-up photograph of fabric, " + ", ".join(p for p in parts if p)


def matches_filters(record, preferences):
    uses = set(record.get("uses", []))
    requested = preferences.fabric_type
    if requested == "both" and not {"main", "sheer"}.issubset(uses):
        return False
    if requested and requested != "both" and requested not in uses:
        return False
    composition = record.get("composition", "").casefold()
    for material in preferences.materials:
        material = material.casefold().strip()
        if material in {"natural", "natural fibres", "natural fibers"}:
            if not any(f in composition for f in ("cotton", "linen", "silk", "wool", "hemp", "jute")):
                return False
            if any(f in composition for f in ("polyester", "nylon", "acrylic", "viscose", "rayon", "elastane")):
                return False
        elif material not in composition:
            return False
    return True


def rank_records(records, vectors, query_vector, preferences, prices, limit):
    price_map = {record_key(p): p for p in prices}
    ranked, seen = [], set()
    for record, vector in zip(records, vectors):
        price = price_map.get(record_key(record))
        if price is None or not matches_filters(record, preferences):
            continue
        if record["id"] in seen or not Path(record["image_path"]).is_file():
            continue
        seen.add(record["id"])
        score = float(np.dot(vector, query_vector))
        if not np.isfinite(score):
            continue
        ranked.append({**record, "price": price["price"], "width": price["width"], "score": score})
    ranked.sort(key=lambda r: (-r["score"], r["id"]))
    return ranked[:limit]


def find_similar(preferences=None, image_path=None, *, limit=None, db_path=None):
    preferences = FabricPreferences.model_validate(preferences or {})
    limit = limit if limit is not None else int(os.getenv("FABRIC_SEARCH_RESULT_COUNT", "5"))
    if not 1 <= limit <= 10:
        raise ValueError("FABRIC_SEARCH_RESULT_COUNT must be between 1 and 10")
    path = Path(db_path or os.getenv("FABRIC_INDEX_PATH", str(DEFAULT_DB)))
    if not path.is_file():
        raise CatalogueNotReady("No fabric photo catalogue has been indexed yet")
    # A fresh read sees importer commits immediately, in every server worker.
    with closing(sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT record, embedding FROM fabrics WHERE model=?", (MODEL_NAME,)).fetchall()
    if not rows:
        raise CatalogueNotReady("The fabric photo catalogue is empty")
    records = [json.loads(r[0]) for r in rows]
    vectors = [np.frombuffer(r[1], dtype=np.float32) for r in rows]
    text = visual_query(preferences)
    if image_path:
        with Image.open(image_path) as image:
            photo = ImageOps.exif_transpose(image).convert("RGB")
            photo.thumbnail((1024, 1024))
            query = encode([photo])[0]
        if any((preferences.description, preferences.colours, preferences.textures, preferences.patterns)):
            query = .75 * query + .25 * encode([text])[0]
            query /= max(float(np.linalg.norm(query)), 1e-8)
    else:
        query = encode([text])[0]
    return rank_records(records, vectors, query, preferences, catalogue_records(), limit)


def match_caption(match, position):
    price = match.get("price")
    price_label = f"₹{price}/m" if price else "Price unavailable"
    width = f"{match['width']} inches" if match.get("width") else "not listed"
    use_labels = {"main": "Main curtain", "sheer": "Sheer curtain", "upholstery": "Upholstery"}
    details = []
    if match.get("uses"):
        details.append("Use: " + ", ".join(use_labels[u] for u in match["uses"] if u in use_labels))
    if match.get("composition"):
        details.append("Composition: " + match["composition"])
    details_text = "\n".join(details)
    return (f"{position}. {match['quality']} · {match['sku']}\n"
            f"Album: {match['album']} | {price_label} | Width: {width}\n"
            f"{details_text}\n"
            f"{match['source_url']}")
