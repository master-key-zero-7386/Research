# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local-only Flask tool for researching Amazon seller listings (AU/US/CA marketplaces). A human runs it on
their own machine, picks a seller ID and a price range in a web UI, and the tool drives a real logged-in
Chrome profile via Selenium to scrape search results into CSV files. There is no production deployment,
no multi-user concern, and no test suite — this is a single-operator desktop utility distributed as a
folder with a bundled embedded Python (`python_embed/`, not tracked in git).

## Running it

```bash
# First-time setup (installs requirements.txt into whichever Python is present)
python setup_env.py          # or setup.bat / setup.command

# Start the app (opens http://127.0.0.1:5002/amazon/ in a browser)
python start_app.py          # or start.bat / start.command
python app.py                # run Flask directly, without the browser-launch wrapper
```

`start_app.py` decides which Python to launch `app.py` with: if `python_embed/` exists (Windows
distribution) it uses the current interpreter; otherwise it falls back to a `venv/` created by
`setup_env.py`. `start_research.bat` is a third path that activates a fixed-path venv at
`C:\python_env\venv` and runs `app.py` directly — a leftover/alternate dev entrypoint, not the one
`setup_env.py` creates.

There are no lint or test commands configured (no test suite exists in this repo).

## Architecture

- **`app.py`** — creates the Flask app, registers the `amazon` blueprint at `/amazon`, and runs
  `amazon/db_migrate.py` on startup to create/update SQLite schemas before serving. The route at `/`
  (not under `/amazon`) just renders `index.html` with empty context — the real UI lives under `/amazon/`.
- **`amazon/routes.py`** — essentially the whole application: seller CRUD against `db/seller_list.db`,
  the `/process` endpoint that shells out to `a_get_seller_items.py` as a subprocess (passing all
  parameters as positional CLI args, not through a shared module), ASIN extraction from saved CSVs, and a
  custom "trash" system (`tool_trash/` + `_manifest.json`) used instead of permanent delete so moved
  files can be restored to their original folder.
- **`amazon/a_get_seller_items.py`** — the actual scraper, run as a standalone script (via
  `subprocess.Popen([sys.executable, script_path] + args)`), not imported. It launches Chrome with a
  **persistent user-data-dir** (`Chrome_Profile/<country>/`, configurable via
  `chrome_profile_<country>` in `config.json`) so the operator's existing Amazon login/session carries
  over. It shows an in-page confirmation banner (injected JS) asking the operator to verify the "Deliver
  to" region before scraping proceeds, builds Amazon search URLs with `rh=p_36:<price*100>-<price*100>`
  price-range filters (stepped in `step_price` increments), paginates up to 20 pages, filters out
  sponsored/best-seller/overall-pick badges, and writes one CSV per price-step to `data/<country>/`.
  Because it's a separate process, communication back to Flask is one-way (fire-and-forget); the web UI
  doesn't await completion, it just redirects.
- **`amazon/brand_master.py`** — resolves a brand name to Amazon's internal `p_123:<brand_id>` filter
  value, caching results in `db/brand_master.db` (`(marketplace, brand_name)` unique) so the same brand
  isn't looked up via a live Selenium search every run.
- **`amazon/db.py` / `amazon/db_migrate.py`** — two independent, near-duplicate `get_conn()` helpers (not
  shared) plus a small hand-rolled migration system: `SELLER_LIST_COLUMNS` / `BRAND_MASTER_COLUMNS` dicts
  define schema, `migrate_table()` creates the table if missing or `ALTER TABLE ADD COLUMN`s anything new,
  then ensures a `UNIQUE INDEX`. There's no migration framework/versioning — schema changes are made by
  editing the column dicts and re-running (idempotent).
- **`utils/config_loader.py`** — loads `config/config.json` once at import time into module-level `cfg`;
  `get_debug_mode()` re-reads the file live so debug logging can be toggled without restarting. Several
  other modules (`amazon/routes.py`, `a_get_seller_items.py`) also read `config.json` directly themselves
  rather than going through this loader — expect config-reading logic duplicated in multiple places.
- **`amazon/constants.py`** — `BASE_DIR`/`CONFIG_PATH`/`UPLOAD_FOLDER` computed relative to the `amazon/`
  package; `routes.py` separately recomputes its own `BASE_DIR` (`os.path.dirname(__file__)`, one level
  different) — the two `BASE_DIR`s are not interchangeable, check which one a given code path uses.
- **Frontend** — single Jinja template (`templates/index.html`) rendered once; all interactivity
  (seller dropdown, running the scrape, ASIN extraction, trash management) is done client-side in
  `static/js/main.js` calling the JSON endpoints in `routes.py`. jQuery + DataTables are pulled from a
  CDN (no bundler/build step). Despite the markup having a `research`/`option` tab structure, both tabs
  are shown on one screen (tab buttons are hidden by inline `style="display:none;"`, a deliberate later
  simplification — don't "fix" this by removing the hidden style without checking with the user first).

## State and storage

- `config/config.json` — runtime settings (`data_dir`, `log_dir`, per-region Chrome profile paths,
  `last_used` form values, `debug` flag). Gitignored; not present until first run.
- `db/seller_list.db`, `db/brand_master.db` — SQLite, schema managed by `db_migrate.py`.
- `data/<region>/` — scraped CSVs and generated `*_ASIN_list.csv` files.
- `Chrome_Profile/<region>/` — persistent Selenium Chrome profiles per marketplace; deleting these loses
  the operator's Amazon login.
- `tool_trash/` — soft-delete holding area with `_manifest.json` recording each file's original folder
  so it can be restored; this is not OS Recycle Bin (`send2trash` is imported in `routes.py` but the
  custom trash dir is what's actually used for the ASIN-file delete flow).

Everything under `config/`, `data/`, `db/*.db`, `log/`, `Chrome_Profile/`, `tool_trash/`, and `uploads/`
is gitignored — these are per-operator runtime state, not fixtures. Don't assume their contents match
what's described above; read them if a task depends on current data.
