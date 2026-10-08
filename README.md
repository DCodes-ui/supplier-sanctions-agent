# Supplier sanctions screening

Screen a supplier against public sanctions lists and get a decision a person can act on: `clear`, `review`, or `likely_hit`. One supplier and a CSV batch use the same path. The lists, the name index, and the screening history stay in a SQLite file on this machine.

This project is non-commercial. That is why the OpenSanctions bulk file is included.

## Run

From the repository root, after the virtualenv in `screener/.venv` exists:

```bash
./screener/.venv/bin/python -m screener api
```

The API listens on `http://127.0.0.1:8000`. The UI, from `web/`:

```bash
npm run dev
```

`npm run dev` at the repository root starts the API and the UI together. Open `http://localhost:3000`.

Put the xAI key in a gitignored `.env` at the repository root:

```bash
XAI_API_KEY=
```

Without that key, screening still runs. The score rules decide, and the result says so.

## Checks

From `screener/`:

```bash
./.venv/bin/python -m pytest
./.venv/bin/python -m screener eval
```

Pytest does not call Grok. The eval scores a fixed set of real listed names against the snapshot already in the database.

## Read next

- [Briefing](docs/BRIEFING.md) for what the system does, the lists, and the eval numbers.
- [Design](docs/DESIGN.md) for the Python layout, the pipeline, and the contracts.
- [Azure](docs/AZURE.md) for how this proof of concept would run in Azure, and what would change.
