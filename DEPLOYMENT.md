# Production deployment

The user authorizes Codex to manage FabricBot deployments end-to-end through
`https://github.com/sid596/FabricBot`. Commit and push application changes before
deploying the same verified commit on the VPS. Do not store credentials in Git.

## Current production inventory

- Host: `64.227.138.31`; SSH administration account: `root`.
- Project: `/opt/fabricbot`; service account: `fabricbot`.
- Active deployment branch: `rich-quotation` (not `main`).
- Python: `/opt/fabricbot/venv/bin/python`; systemd service: `fabricbot`.
- Application listener: `127.0.0.1:5000`.
- Public hostname: `https://fabricbot.grihamdecor.in`.
- Price credentials: existing `.env` and `fabricbot.json`, kept on the server.
- Image catalogue: `/opt/fabricbot/data/fabrics.sqlite3` and `data/photos/`.
- Model cache: service account's Hugging Face cache, outside Git.

## Routing boundary

Nginx sends `/webhook` to the existing gateway on port 8766. Registered staff
outside an Operations conversation go to FabricBot. Allowlisted developers enter
FabricBot by sending `fabricbot`; `exit`, `public`, or `angie` leaves that session.
Other customer leads go to a separate customer Angie service. Deploying this
repository does not change those routing rules. The Operations, gateway, customer
bot, dashboard and their configuration are separate services; inspect their
ownership and intended routing before changing them.

## Update procedure

1. Check the current local and server Git commits, tracked-file changes, service
   status, free memory/disk and running dependencies. Preserve untracked server
   files; do not upload the local working directory over production.
2. Run local tests. Commit the intended changes on the working branch and push
   to this repository. Record the old and new commit IDs.
3. On the VPS, fetch that branch and fast-forward to the intended commit. Verify
   `git rev-parse HEAD` equals the pushed commit. Stop if tracked production files
   have local changes or the update is not a fast-forward.
4. Install changed requirements into the service's virtual environment and run
   `python -m pip check`. Preserve credentials. For dependency changes, prepare
   a separate environment and retain the previous one until validation passes.
5. Prepare catalogue assets separately from Git. Rebuild with `catalogue_import.py`
   or transfer a consistent SQLite backup plus photos, then rebase each stored
   `image_path` to its verified server photo. Check database integrity, image
   existence and service-account permissions before making the catalogue active.
6. The image model needs memory beyond the existing web services. On the current
   2 GB host, `ops/prepare_vps_memory.sh` provisions 2 GB swap if none is enabled.
   Warm the pinned CLIP model as `fabricbot`, with bounded CPU threads. Check an
   image self-match and a five-result text query. Do not send test WhatsApp messages
   without explicit authorization.
7. Check PDF generation and live Sheets reads as `fabricbot`, restart only the
   `fabricbot` service, then verify systemd, the loopback and public HTTP endpoint,
   and recent service errors. Record the deployed commit and catalogue counts.
8. If application health fails, restore the recorded application commit and prior
   environment/catalogue, restart FabricBot and verify recovery. Do not roll back
   unrelated services. Keep the prior revision available until verification ends.

`deploy_fabricbot.sh` is an old first-install bootstrap that replaces the app
directory and configures Nginx. **Do not run it against this existing VPS.**

A successful HTTP check alone does not prove model search or WhatsApp delivery.
Report the specific checks completed and any untested or inaccessible paths.
