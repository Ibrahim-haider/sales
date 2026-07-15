# Universal Excel Analytics Platform

A working React + FastAPI prototype for internal Excel/CSV analysis.

## Included

- Excel/CSV upload
- Multiple-sheet Excel detection
- Data preview
- Automatic column recognition
- Manual column mapping
- Spreadsheet-style data grid
- Sorting, floating filters, resizing and pagination
- Advanced filter builder
- Calculated numeric columns
- Group-by analysis
- Sum, average, count, min, max, median and distinct count
- Bar, line and pie charts
- CSV and Excel export

## Supported files

- `.xlsx`
- `.xls`
- `.csv`

The file must contain structured tabular data. The system does not execute Excel macros or interpret images/unstructured documents.

## Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URL: `http://localhost:8000`

## Run the frontend

Install Node.js first, then:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

## Calculated-column examples

```text
Sales - Cost
Sales / Target * 100
Cash + Installment
round(Sales / 1000000, 2)
```

Column names with spaces may need to be renamed or mapped to simpler names before formulas are used.

## Important prototype note

Sessions are stored in backend memory. Restarting the backend clears uploaded data. For shared departmental deployment, add PostgreSQL/object storage and authentication.
