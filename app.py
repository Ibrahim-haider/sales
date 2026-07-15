
from __future__ import annotations

import io
import re
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(
    page_title="Automatic Excel Analysis",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
.block-container {padding-top:1rem; padding-bottom:2rem;}
.hero {
  padding:22px 24px;
  border-radius:18px;
  background:linear-gradient(135deg,#10284d,#2563eb);
  color:white;
  margin-bottom:18px;
}
.hero h1 {margin:0 0 6px;}
.hero p {margin:0; opacity:.9;}
[data-testid="stMetric"] {
  background:white;
  border:1px solid #dce4ef;
  border-radius:14px;
  padding:14px;
}
.section {
  background:#1f3d6d;
  color:white;
  padding:8px 12px;
  border-radius:7px;
  font-weight:700;
  margin:16px 0 12px;
}
.insight {
  background:white;
  border-left:4px solid #2563eb;
  padding:10px 13px;
  margin:7px 0;
  border-radius:7px;
}
</style>

<div class="hero">
  <h1>Automatic Excel Analysis</h1>
  <p>Upload a structured Excel or CSV file. The system automatically profiles the data, calculates key metrics, creates charts, and highlights important findings.</p>
</div>
""", unsafe_allow_html=True)

def parse_file(uploaded):
    raw = uploaded.getvalue()
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return {"Data": pd.read_csv(io.BytesIO(raw))}
    xls = pd.ExcelFile(io.BytesIO(raw))
    return {sheet: pd.read_excel(io.BytesIO(raw), sheet_name=sheet) for sheet in xls.sheet_names}

def clean_name(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v).strip().lower()).strip()

def detect_types(df):
    date_cols, numeric_cols, categorical_cols, text_cols = [], [], [], []
    for col in df.columns:
        s = df[col]
        # date detection
        if pd.api.types.is_datetime64_any_dtype(s):
            date_cols.append(col)
            continue
        parsed_dates = pd.to_datetime(s, errors="coerce")
        if len(s) and parsed_dates.notna().mean() >= 0.8 and s.nunique(dropna=True) > 3:
            date_cols.append(col)
            continue
        # numeric detection
        numeric = pd.to_numeric(s, errors="coerce")
        if len(s) and numeric.notna().mean() >= 0.8:
            numeric_cols.append(col)
            continue
        unique = s.nunique(dropna=True)
        if unique <= 50:
            categorical_cols.append(col)
        else:
            text_cols.append(col)
    return date_cols, numeric_cols, categorical_cols, text_cols

def likely_column(columns, aliases):
    normalized = {clean_name(c): c for c in columns}
    for alias in aliases:
        if clean_name(alias) in normalized:
            return normalized[clean_name(alias)]
    for col in columns:
        n = clean_name(col)
        if any(clean_name(a) in n or n in clean_name(a) for a in aliases):
            return col
    return None

def money(v):
    v = float(v)
    if abs(v) >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:,.0f}"

def to_excel_bytes(df):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Analyzed Data")
    return bio.getvalue()

uploaded = st.file_uploader(
    "Upload Excel or CSV",
    type=["xlsx", "xls", "csv"],
    help="Best results come from structured tables with one header row.",
)

if uploaded is None:
    st.info("Upload a file to generate the analysis automatically.")
    st.stop()

try:
    sheets = parse_file(uploaded)
except Exception as exc:
    st.error(f"Could not read the file: {exc}")
    st.stop()

sheet_name = st.selectbox("Select sheet", list(sheets))
df = sheets[sheet_name].copy()

# Remove completely blank rows/columns automatically
df = df.dropna(how="all").dropna(axis=1, how="all")
df.columns = [str(c).strip() for c in df.columns]

if df.empty:
    st.error("The selected sheet has no usable data.")
    st.stop()

date_cols, numeric_cols, categorical_cols, text_cols = detect_types(df)

# Convert detected columns
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")
for col in date_cols:
    df[col] = pd.to_datetime(df[col], errors="coerce")

# Identify common business fields
sales_col = likely_column(df.columns, ["sales", "sale value", "sales value", "net sales", "actual sales", "sv", "revenue"])
target_col = likely_column(df.columns, ["target", "sales target", "mtd target", "monthly target"])
cash_col = likely_column(df.columns, ["cash", "cash sales", "cash sale value"])
installment_col = likely_column(df.columns, ["installment", "installments", "hp", "hire purchase"])
branch_col = likely_column(df.columns, ["branch", "branch name", "store", "store name", "outlet"])
zone_col = likely_column(df.columns, ["zone", "region", "area", "territory"])
qty_col = likely_column(df.columns, ["quantity", "qty", "units", "units sold"])
date_col = date_cols[0] if date_cols else None

# KPI overview
st.markdown('<div class="section">Automatic Overview</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{len(df):,}")
c2.metric("Columns", len(df.columns))
c3.metric("Missing Cells", f"{int(df.isna().sum().sum()):,}")
c4.metric("Duplicate Rows", f"{int(df.duplicated().sum()):,}")

# Business KPIs when recognized
business_metrics = []
if sales_col:
    business_metrics.append(("Total Sales", money(df[sales_col].sum())))
if target_col:
    business_metrics.append(("Total Target", money(df[target_col].sum())))
if sales_col and target_col and df[target_col].sum():
    business_metrics.append(("Achievement", f"{df[sales_col].sum()/df[target_col].sum()*100:.1f}%"))
if cash_col:
    business_metrics.append(("Cash Sales", money(df[cash_col].sum())))
if installment_col:
    business_metrics.append(("Installment Sales", money(df[installment_col].sum())))
if qty_col:
    business_metrics.append(("Total Quantity", f"{df[qty_col].sum():,.0f}"))

if business_metrics:
    cols = st.columns(min(4, len(business_metrics)))
    for i, (label, value) in enumerate(business_metrics):
        cols[i % len(cols)].metric(label, value)

# Auto insights
st.markdown('<div class="section">Automatic Findings</div>', unsafe_allow_html=True)
insights = []

if numeric_cols:
    for col in numeric_cols[:5]:
        s = df[col].dropna()
        if len(s):
            insights.append(f"{col}: average {money(s.mean())}, minimum {money(s.min())}, maximum {money(s.max())}.")

if sales_col and branch_col:
    branch_sales = df.groupby(branch_col, dropna=False)[sales_col].sum().sort_values(ascending=False)
    if len(branch_sales):
        insights.append(f"Highest contributor: {branch_sales.index[0]} with {money(branch_sales.iloc[0])}.")
        insights.append(f"Lowest contributor: {branch_sales.index[-1]} with {money(branch_sales.iloc[-1])}.")

if sales_col and target_col:
    temp = df[[sales_col, target_col]].dropna()
    if len(temp):
        above = (temp[sales_col] >= temp[target_col]).sum()
        below = (temp[sales_col] < temp[target_col]).sum()
        insights.append(f"{above} records are meeting or exceeding target; {below} are below target.")

if cash_col and installment_col:
    cash = df[cash_col].sum()
    inst = df[installment_col].sum()
    total = cash + inst
    if total:
        insights.append(f"Cash contributes {cash/total*100:.1f}% while installments contribute {inst/total*100:.1f}%.")

if date_col and sales_col:
    trend = df.dropna(subset=[date_col]).groupby(df[date_col].dt.to_period("M"))[sales_col].sum()
    if len(trend) >= 2:
        change = (trend.iloc[-1] - trend.iloc[-2]) / abs(trend.iloc[-2]) * 100 if trend.iloc[-2] else 0
        insights.append(f"Latest period changed by {change:.1f}% compared with the previous period.")

if not insights:
    insights.append("The file was loaded successfully, but no standard sales fields were recognized. Generic profiling and charts are still available.")

for item in insights:
    st.markdown(f'<div class="insight">{item}</div>', unsafe_allow_html=True)

# Automatic charts
st.markdown('<div class="section">Automatically Generated Charts</div>', unsafe_allow_html=True)

chart_count = 0

if sales_col and branch_col:
    chart_df = (
        df.groupby(branch_col, dropna=False)[sales_col]
        .sum()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
    )
    fig = px.bar(chart_df, x=branch_col, y=sales_col, title=f"Top {branch_col} by {sales_col}")
    st.plotly_chart(fig, use_container_width=True)
    chart_count += 1

if sales_col and target_col and branch_col:
    chart_df = df.groupby(branch_col, dropna=False)[[sales_col, target_col]].sum().reset_index()
    fig = px.bar(
        chart_df,
        x=branch_col,
        y=[sales_col, target_col],
        barmode="group",
        title="Actual vs Target",
    )
    st.plotly_chart(fig, use_container_width=True)
    chart_count += 1

if cash_col and installment_col:
    mix = pd.DataFrame({
        "Payment Type": ["Cash", "Installment"],
        "Value": [df[cash_col].sum(), df[installment_col].sum()],
    })
    fig = px.pie(mix, names="Payment Type", values="Value", hole=0.5, title="Cash vs Installment")
    st.plotly_chart(fig, use_container_width=True)
    chart_count += 1

if date_col and sales_col:
    trend = (
        df.dropna(subset=[date_col])
        .groupby(df[date_col].dt.date)[sales_col]
        .sum()
        .reset_index()
    )
    fig = px.line(trend, x=date_col, y=sales_col, markers=True, title="Sales Trend")
    st.plotly_chart(fig, use_container_width=True)
    chart_count += 1

if chart_count == 0 and numeric_cols and categorical_cols:
    cat = categorical_cols[0]
    num = numeric_cols[0]
    chart_df = df.groupby(cat, dropna=False)[num].sum().sort_values(ascending=False).head(15).reset_index()
    fig = px.bar(chart_df, x=cat, y=num, title=f"{num} by {cat}")
    st.plotly_chart(fig, use_container_width=True)

# Generic numeric summary
st.markdown('<div class="section">Numeric Summary</div>', unsafe_allow_html=True)
if numeric_cols:
    summary = df[numeric_cols].describe().T.reset_index().rename(columns={"index": "Column"})
    st.dataframe(summary, use_container_width=True, hide_index=True)
else:
    st.info("No numeric columns were detected.")

# Missing data analysis
st.markdown('<div class="section">Data Quality</div>', unsafe_allow_html=True)
quality = pd.DataFrame({
    "Column": df.columns,
    "Missing Values": [int(df[c].isna().sum()) for c in df.columns],
    "Missing %": [round(df[c].isna().mean() * 100, 2) for c in df.columns],
    "Unique Values": [int(df[c].nunique(dropna=True)) for c in df.columns],
    "Detected Type": [
        "Date" if c in date_cols else "Numeric" if c in numeric_cols else "Category" if c in categorical_cols else "Text"
        for c in df.columns
    ],
})
st.dataframe(quality, use_container_width=True, hide_index=True)

# Excel-like data table
st.markdown('<div class="section">Interactive Data Table</div>', unsafe_allow_html=True)
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_default_column(sortable=True, filter=True, resizable=True, floatingFilter=True)
gb.configure_pagination(enabled=True, paginationPageSize=50)
gb.configure_side_bar()
AgGrid(df, gridOptions=gb.build(), height=600, theme="streamlit")

# Downloads
st.markdown('<div class="section">Download Results</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
c1.download_button(
    "Download Cleaned CSV",
    df.to_csv(index=False).encode("utf-8"),
    "cleaned_data.csv",
    "text/csv",
    use_container_width=True,
)
c2.download_button(
    "Download Cleaned Excel",
    to_excel_bytes(df),
    "cleaned_data.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.caption("Automatic analysis works best with structured tabular data and recognizable business columns.")
