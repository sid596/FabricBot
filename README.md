# FabricBot / Angie

Angie reads a WhatsApp text or photo, extracts a structured request with Gemini,
then uses Python for catalogue lookup and deterministic quotation calculations.

## Local setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-visual.txt
# Copy .env.example to .env only if you do not already have a .env file.
# Fill in your existing credentials; put the service-account JSON in fabricbot.json.
.venv/bin/python catalogue_import.py --all
.venv/bin/flask --app server run --port 5000
```

Keep `.env`, `fabricbot.json`, `data/` and downloaded model weights out of Git.
The service account needs read access to the price workbook. This project uses
service-account credentials, not an OAuth link to a particular spreadsheet.
`GOOGLE_SHEET_ID` selects an exact workbook if set; otherwise the existing
`Curtains Q2 and July 2025` / `data` configuration remains the default.

## PDF quotations

A completed quotation is sent as a PDF document, with line items, GST, totals,
and assumptions from the existing calculator. Clarifications and price lookups
remain text messages. PDFs are built in memory, uploaded through the WhatsApp
media API, and sent using the returned media ID. No public document host is needed.
The bundled Noto Sans fonts include the rupee symbol (license in `assets/fonts/`).
Customer-uploaded temporary photos are deleted after processing.

## Refresh without restarting

- Sheet prices refresh on the first request after the configured TTL (default
  five minutes). Concurrent requests in one worker share one complete snapshot.
  A failed refresh surfaces an error instead of silently quoting old prices.
  Each Gunicorn worker maintains its own bounded cache.
- Gemini prompt caches renew before expiry. If a cache has been removed remotely,
  the request retries once using the full instructions. Cache creation failures
  also fall back to the full instructions.
- Photo index updates are read from SQLite on each search. Successful importer
  commits are usable immediately by all workers.

## Photo and description search

Examples:

- Send a close-up fabric photo, optionally captioned `Find similar sheer fabrics`.
- `Show sage green linen-look curtains`.
- `Find pastel floral sheers`.
- `Teal geometric fabric for main curtains`.

Angie returns five nearest available **SKU photos**, each with quality, album,
SKU, current sheet price and source link. It can return multiple colours of one
quality. If fewer photos satisfy the requested usage/material, it says so and
returns those available; it never duplicates photos to fill five slots.

CLIP runs locally for photo-to-photo and text-to-photo similarity. Gemini extracts
text preferences and interprets incoming images. Exact colour words are retained;
related sea-green shades can also appear. Colour/texture/pattern are similarity
preferences, not guarantees of an exact match. Lighting, background and printed
labels affect results; a close crop of the fabric works best. Scores are not shown
as probabilities. Actual fibre requests use source composition; a linen *look*
does not imply linen fibre. Usage filters distinguish main, sheer, both, upholstery.
Unknown use is excluded from explicit usage searches. A fabric must be tagged with
both main and sheer to satisfy `both`.

### Building and updating the source catalogue

```sh
# Small import to check setup
.venv/bin/python catalogue_import.py --collection abaca
# All website collections that exactly match the price sheet
.venv/bin/python catalogue_import.py --all
# Re-read source metadata and recompute existing records
.venv/bin/python catalogue_import.py --all --refresh
```

The importer follows Nuhome's collection/pattern pages, paginated SKU listings,
and each pattern's complete colour-variant list. Brand,
album and quality must match the sheet after case/punctuation normalization.
Unmatched collections/qualities and failed downloads go into
`data/import-report.json`; there are no guessed joins. Photo files and vectors
are resumable. Regular runs reuse cached source pages; use `--refresh` to discover
new variants and metadata changes. Website removal is not treated as proof of
stock unavailability; availability is not modelled. Prices are joined at search
time, never copied from the website. New import commits require no server restart.

The first import downloads CLIP weights (~600 MB) and may take time. Install the
visual dependencies on the machine doing both indexing and serving; allow memory
for the model per worker (start with one worker). SQLite index records contain
local photo paths, so rebuild on another machine rather than copying only the DB.
Importing the catalogue can run separately from the WhatsApp server. An optional
scheduled job can run the same `--all --refresh` command; none is installed here.

## Verification

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python test_quotation.py
```

Tests mock Gemini, Google Sheets and WhatsApp; they do not contact customers.
Live photo-index verification and PDF rendering are separate local checks.
Deploying the new code still requires the usual one-time application reload;
subsequent cache refreshes do not. This change does not deploy or push anything.

## Production deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Git-based update procedure, VPS/service
inventory, verification steps and the shared WhatsApp gateway routing boundary.
