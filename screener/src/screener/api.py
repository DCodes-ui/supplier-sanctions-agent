"""HTTP API for one screen, a CSV batch, history, and the current snapshot."""

from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import Response

from screener.domain.models import ScreeningInput
from screener.matching.index import SnapshotNotReady
from screener.pipeline.screen import (
    StoredScreen,
    dataset_status,
    get_screening,
    list_screenings,
    parse_batch_csv,
    refresh_datasets,
    run_batch,
    run_screen,
    screenings_csv,
)

app = FastAPI(title="Supplier sanctions screening")


@app.post("/screen")
def screen(body: ScreeningInput) -> dict:
    try:
        stored = run_screen(
            body.name,
            body.country,
            body.registration_number,
            body.supplier_id,
        )
    except SnapshotNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _public(stored)


@app.post("/batch", response_model=None)
async def batch(
    file: UploadFile,
    source: str = Form(...),
    format: str = "json",
) -> Response | list[dict]:
    if source not in {"eu_fsf", "ofac_sdn", "opensanctions"}:
        raise HTTPException(status_code=400, detail="Choose EU, OFAC SDN, or OpenSanctions.")
    text = (await file.read()).decode("utf-8-sig")
    try:
        rows = parse_batch_csv(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        stored = run_batch(rows, source=source)
    except SnapshotNotReady as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if format == "csv":
        return Response(screenings_csv(stored), media_type="text/csv")
    return [_public(item) for item in stored]


@app.get("/screenings")
def screenings(limit: int = 50) -> list[dict]:
    return [record.model_dump(mode="json") for record in list_screenings(limit)]


@app.get("/screenings/{screening_id}")
def screening(screening_id: str) -> dict:
    record = get_screening(screening_id)
    if record is None:
        raise HTTPException(status_code=404, detail="screening not found")
    return record.model_dump(mode="json")


@app.get("/datasets")
def datasets() -> dict:
    return dataset_status()


@app.post("/datasets/refresh")
def refresh() -> dict:
    return refresh_datasets()


def _public(stored: StoredScreen) -> dict:
    payload = stored.record.model_dump(mode="json")
    payload["adjudication"] = stored.adjudication
    return payload
