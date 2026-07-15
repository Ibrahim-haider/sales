
from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .models import (
    AggregateRequest,
    CalculatedColumnRequest,
    ExportRequest,
    FilterRequest,
    MappingRequest,
)
from .store import SESSIONS, SessionData
from .utils import (
    add_calculated_column,
    apply_filters,
    dataframe_to_records,
    detect_column_types,
    infer_mapping,
)

app = FastAPI(title="Universal Excel Analytics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_session(session_id: str) -> SessionData:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(status_code=400, detail="Supported formats: .xlsx, .xls, .csv")

    content = await file.read()
    sheets: dict[str, pd.DataFrame] = {}

    try:
        if suffix == ".csv":
            sheets["Data"] = pd.read_csv(io.BytesIO(content))
        else:
            workbook = pd.ExcelFile(io.BytesIO(content))
            for sheet in workbook.sheet_names:
                sheets[sheet] = pd.read_excel(io.BytesIO(content), sheet_name=sheet)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}") from exc

    if not sheets:
        raise HTTPException(status_code=400, detail="No readable data found.")

    session_id = str(uuid.uuid4())
    active_sheet = next(iter(sheets))
    SESSIONS[session_id] = SessionData(
        filename=file.filename or "uploaded_file",
        sheets=sheets,
        active_sheet=active_sheet,
    )

    df = sheets[active_sheet]
    return {
        "session_id": session_id,
        "filename": file.filename,
        "sheets": list(sheets.keys()),
        "active_sheet": active_sheet,
        "rows": len(df),
        "columns": [str(c) for c in df.columns],
        "column_types": detect_column_types(df),
        "suggested_mapping": infer_mapping(df.columns),
        "preview": dataframe_to_records(df.head(50)),
    }


@app.get("/sheet/{session_id}/{sheet_name}")
def select_sheet(session_id: str, sheet_name: str):
    session = get_session(session_id)
    if sheet_name not in session.sheets:
        raise HTTPException(status_code=404, detail="Sheet not found.")
    session.active_sheet = sheet_name
    df = session.sheets[sheet_name]
    return {
        "active_sheet": sheet_name,
        "rows": len(df),
        "columns": [str(c) for c in df.columns],
        "column_types": detect_column_types(df),
        "suggested_mapping": infer_mapping(df.columns),
        "preview": dataframe_to_records(df.head(50)),
    }


@app.post("/mapping")
def save_mapping(request: MappingRequest):
    session = get_session(request.session_id)
    session.mappings[session.active_sheet] = request.mapping
    return {"status": "saved", "mapping": request.mapping}


@app.post("/data")
def get_data(request: FilterRequest):
    session = get_session(request.session_id)
    df = session.sheets[session.active_sheet]
    filtered = apply_filters(df, request.filters)

    if request.sort_by and request.sort_by in filtered.columns:
        filtered = filtered.sort_values(
            request.sort_by,
            ascending=request.sort_direction.lower() != "desc",
            na_position="last",
        )

    page_size = max(1, min(request.page_size, 1000))
    page = max(1, request.page)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "total_rows": len(filtered),
        "page": page,
        "page_size": page_size,
        "columns": [str(c) for c in filtered.columns],
        "column_types": detect_column_types(filtered),
        "records": dataframe_to_records(filtered.iloc[start:end]),
    }


@app.post("/calculated-column")
def calculated_column(request: CalculatedColumnRequest):
    session = get_session(request.session_id)
    sheet = session.active_sheet
    df = session.sheets[sheet]
    try:
        updated = add_calculated_column(df, request.name, request.expression)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.sheets[sheet] = updated
    return {
        "status": "created",
        "column": request.name,
        "columns": [str(c) for c in updated.columns],
        "preview": dataframe_to_records(updated.head(50)),
    }


@app.post("/aggregate")
def aggregate(request: AggregateRequest):
    session = get_session(request.session_id)
    df = apply_filters(session.sheets[session.active_sheet], request.filters)

    group_by = [c for c in request.group_by if c in df.columns]
    named_aggs: dict[str, Any] = {}

    for metric in request.metrics:
        column = metric.get("column")
        operation = metric.get("operation", "sum")
        alias = metric.get("alias") or f"{operation}_{column}"
        if column not in df.columns:
            continue
        if operation not in {"sum", "mean", "count", "min", "max", "median", "nunique"}:
            raise HTTPException(status_code=400, detail=f"Unsupported operation: {operation}")
        named_aggs[alias] = pd.NamedAgg(column=column, aggfunc=operation)

    if not named_aggs:
        raise HTTPException(status_code=400, detail="Add at least one valid metric.")

    if group_by:
        result = df.groupby(group_by, dropna=False).agg(**named_aggs).reset_index()
    else:
        result = pd.DataFrame([{alias: getattr(df[agg.column], agg.aggfunc)() for alias, agg in named_aggs.items()}])

    return {
        "columns": [str(c) for c in result.columns],
        "records": dataframe_to_records(result),
    }


@app.post("/export")
def export_data(request: ExportRequest):
    session = get_session(request.session_id)
    df = apply_filters(session.sheets[session.active_sheet], request.filters)
    fmt = request.format.lower()

    if fmt == "csv":
        payload = df.to_csv(index=False).encode("utf-8")
        media_type = "text/csv"
        filename = "filtered_data.csv"
    elif fmt == "xlsx":
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Filtered Data")
        payload = bio.getvalue()
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "filtered_data.xlsx"
    else:
        raise HTTPException(status_code=400, detail="Export format must be csv or xlsx.")

    return StreamingResponse(
        io.BytesIO(payload),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
