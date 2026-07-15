
from __future__ import annotations

import io
import re
from calendar import monthrange
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(
    page_title="Sales Intelligence Portal",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
.hero {
  padding: 20px 24px;
  border-radius: 16px;
  color: white;
  background: linear-gradient(135deg,#17355f,#2f6ba5);
  margin-bottom: 16px;
}
.hero h1 {margin:0 0 5px;}
.hero p {margin:0; opacity:.9;}
.section {
  background:#1F4E78;
  color:white;
  padding:8px 12px;
  border-radius:6px;
  font-weight:700;
  margin:16px 0 12px;
}
[data-testid="stMetric"] {
  background:white;
  border:1px solid #dce3ec;
  border-radius:12px;
  padding:13px;
}
.insight {
  background:white;
  border-left:4px solid #2f6ba5;
  padding:10px 13px;
  border-radius:7px;
  margin:7px 0;
}
</style>

<div class="hero">
  <h1>Sales Intelligence Portal</h1>
  <p>Upload the monthly sales workbook. The system identifies the reporting and transaction sheets and generates the analysis automatically.</p>
</div>
""", unsafe_allow_html=True)

WORKING_REQUIRED = [
    "Unit","Store","Zone","Branch Name","Target","Sale Value",
    "YTD TGT","YTD SV","CS TGT","Cash","HP"
]
RAW_HINTS = ["SALESID","STORE","INVOICEID","INVOICEDATE","SALESDATE","SV","Date"]

def money(value: Any) -> str:
    try:
        value = float(value)
    except Exception:
        return "0"
    if abs(value) >= 1_000_000_000:
        return f"Rs. {value/1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"Rs. {value/1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"Rs. {value/1_000:.1f}K"
    return f"Rs. {value:,.0f}"

def safe_ratio(a, b):
    return a / b if b else 0

def detect_header_row(raw_df: pd.DataFrame, expected_columns: list[str], max_rows: int = 20) -> int:
    best_row, best_score = 0, -1
    expected = {str(x).strip().lower() for x in expected_columns}
    for row_idx in range(min(max_rows, len(raw_df))):
        values = {str(v).strip().lower() for v in raw_df.iloc[row_idx].dropna()}
        score = len(values.intersection(expected))
        if score > best_score:
            best_score = score
            best_row = row_idx
    return best_row

def read_workbook(uploaded):
    content = uploaded.getvalue()
    xls = pd.ExcelFile(io.BytesIO(content))
    sheets = {}
    for sheet in xls.sheet_names:
        preview = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=None, nrows=25)
        working_score = max(
            len(set(str(v).strip() for v in preview.iloc[i].dropna()).intersection(WORKING_REQUIRED))
            for i in range(min(20, len(preview)))
        )
        raw_score = max(
            len(set(str(v).strip() for v in preview.iloc[i].dropna()).intersection(RAW_HINTS))
            for i in range(min(10, len(preview)))
        )

        if working_score >= 5:
            header_row = detect_header_row(preview, WORKING_REQUIRED)
        elif raw_score >= 4:
            header_row = detect_header_row(preview, RAW_HINTS, 10)
        else:
            header_row = 0

        sheets[sheet] = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=header_row)
    return sheets

def clean_columns(df):
    out = df.copy()
    out = out.loc[:, ~out.columns.astype(str).str.startswith("Unnamed")]
    out = out.dropna(how="all").dropna(axis=1, how="all")
    out.columns = [str(c).strip() for c in out.columns]
    return out

def identify_sheets(sheets):
    working_name, raw_name = None, None
    for name, df in sheets.items():
        cols = set(df.columns.astype(str))
        if len(cols.intersection(WORKING_REQUIRED)) >= 7:
            working_name = name
        if len(cols.intersection(RAW_HINTS)) >= 4:
            raw_name = name
    return working_name, raw_name

def numeric(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def excel_bytes(df, sheet_name="Analysis"):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return bio.getvalue()

uploaded = st.file_uploader(
    "Upload monthly sales workbook",
    type=["xlsx","xls"],
    help="The app is optimized for workbooks containing a reporting sheet and a raw transaction sheet.",
)

if uploaded is None:
    st.info("Upload the workbook to generate the analysis.")
    st.stop()

try:
    sheets = read_workbook(uploaded)
    sheets = {name: clean_columns(df) for name, df in sheets.items()}
except Exception as exc:
    st.error(f"Could not read workbook: {exc}")
    st.stop()

working_name, raw_name = identify_sheets(sheets)

if not working_name:
    st.error("A reporting sheet with fields such as Unit, Store, Zone, Target and Sale Value could not be identified.")
    st.stop()

working = sheets[working_name].copy()
raw = sheets[raw_name].copy() if raw_name else None

working = numeric(
    working,
    ["Target","Sale Value","ACH%","YTD TGT","YTD SV","YTD ACH",
     "CS TGT","HP TGT","Cash","HP","HP ACH","LDS","PDR","TDS",
     "GP","NP","Ex-Due","OD"]
)

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    st.success(f"Reporting sheet: {working_name}")
    if raw_name:
        st.success(f"Transaction sheet: {raw_name}")

    filtered = working.copy()

    for field in ["Unit","Zone","Store","Branch Name","Branch Category"]:
        if field in filtered.columns:
            options = sorted(filtered[field].dropna().astype(str).unique().tolist())
            selected = st.multiselect(field, options, default=options)
            if selected:
                filtered = filtered[filtered[field].astype(str).isin(selected)]
            else:
                filtered = filtered.iloc[0:0]

if filtered.empty:
    st.warning("No rows match the selected filters.")
    st.stop()

# Main KPI calculations
mtd_target = filtered["Target"].sum() if "Target" in filtered else 0
mtd_sales = filtered["Sale Value"].sum() if "Sale Value" in filtered else 0
mtd_ach = safe_ratio(mtd_sales, mtd_target)

ytd_target = filtered["YTD TGT"].sum() if "YTD TGT" in filtered else 0
ytd_sales = filtered["YTD SV"].sum() if "YTD SV" in filtered else 0
ytd_ach = safe_ratio(ytd_sales, ytd_target)

cash_target = filtered["CS TGT"].sum() if "CS TGT" in filtered else 0
cash_sales = filtered["Cash"].sum() if "Cash" in filtered else 0
cash_ach = safe_ratio(cash_sales, cash_target)

hp_target = filtered["HP TGT"].sum() if "HP TGT" in filtered else 0
hp_sales = filtered["HP"].sum() if "HP" in filtered else 0
hp_ach = safe_ratio(hp_sales, hp_target)

# Determine date for run rate
date_col = None
as_of = pd.Timestamp.today()
if raw is not None:
    for c in ["Date","INVOICEDATE","SALESDATE"]:
        if c in raw.columns:
            dates = pd.to_datetime(raw[c], errors="coerce").dropna()
            if len(dates):
                date_col = c
                as_of = dates.max()
                break

days_in_month = monthrange(as_of.year, as_of.month)[1]
elapsed_days = max(as_of.day, 1)
remaining_days = max(days_in_month - elapsed_days, 0)
current_run_rate = safe_ratio(mtd_sales, elapsed_days)
required_run_rate = safe_ratio(max(mtd_target - mtd_sales, 0), remaining_days)
risk_ratio = safe_ratio(current_run_rate, required_run_rate)
risk = "Low" if risk_ratio >= 1 else "Medium" if risk_ratio >= 0.8 else "High"

st.markdown('<div class="section">Executive Summary</div>', unsafe_allow_html=True)
k1,k2,k3,k4 = st.columns(4)
k1.metric("MTD Sales", money(mtd_sales))
k2.metric("MTD Target", money(mtd_target))
k3.metric("MTD Achievement", f"{mtd_ach*100:.1f}%")
k4.metric("Days Remaining", remaining_days)

k5,k6,k7,k8 = st.columns(4)
k5.metric("YTD Sales", money(ytd_sales))
k6.metric("YTD Achievement", f"{ytd_ach*100:.1f}%")
k7.metric("Current Run Rate", money(current_run_rate))
k8.metric("Required Run Rate", money(required_run_rate), f"Risk: {risk}")

k9,k10,k11,k12 = st.columns(4)
k9.metric("Cash Sales", money(cash_sales))
k10.metric("Cash Achievement", f"{cash_ach*100:.1f}%")
k11.metric("Installment Sales", money(hp_sales))
k12.metric("Installment Achievement", f"{hp_ach*100:.1f}%")

# Zone summary
st.markdown('<div class="section">Zone Performance</div>', unsafe_allow_html=True)
zone_summary = (
    filtered.groupby("Zone", dropna=False)
    .agg({
        "Target":"sum",
        "Sale Value":"sum",
        "CS TGT":"sum",
        "Cash":"sum",
        "HP TGT":"sum",
        "HP":"sum",
        "YTD TGT":"sum",
        "YTD SV":"sum",
    })
    .reset_index()
)
zone_summary["MTD Achievement %"] = zone_summary["Sale Value"] / zone_summary["Target"].replace(0, np.nan) * 100
zone_summary["Cash Achievement %"] = zone_summary["Cash"] / zone_summary["CS TGT"].replace(0, np.nan) * 100
zone_summary["HP Achievement %"] = zone_summary["HP"] / zone_summary["HP TGT"].replace(0, np.nan) * 100
zone_summary["YTD Achievement %"] = zone_summary["YTD SV"] / zone_summary["YTD TGT"].replace(0, np.nan) * 100
zone_summary = zone_summary.fillna(0)

st.dataframe(
    zone_summary.style.format({
        "Target":"{:,.0f}",
        "Sale Value":"{:,.0f}",
        "CS TGT":"{:,.0f}",
        "Cash":"{:,.0f}",
        "HP TGT":"{:,.0f}",
        "HP":"{:,.0f}",
        "YTD TGT":"{:,.0f}",
        "YTD SV":"{:,.0f}",
        "MTD Achievement %":"{:.1f}%",
        "Cash Achievement %":"{:.1f}%",
        "HP Achievement %":"{:.1f}%",
        "YTD Achievement %":"{:.1f}%",
    }),
    use_container_width=True,
    hide_index=True,
)

left, right = st.columns(2)
with left:
    chart_df = zone_summary.melt(
        id_vars="Zone",
        value_vars=["Target","Sale Value"],
        var_name="Metric",
        value_name="Value",
    )
    fig = px.bar(chart_df, x="Zone", y="Value", color="Metric", barmode="group", title="MTD Target vs Sales")
    st.plotly_chart(fig, use_container_width=True)

with right:
    ach_df = zone_summary.melt(
        id_vars="Zone",
        value_vars=["MTD Achievement %","YTD Achievement %"],
        var_name="Metric",
        value_name="Achievement",
    )
    fig = px.line(ach_df, x="Zone", y="Achievement", color="Metric", markers=True, title="MTD vs YTD Achievement")
    st.plotly_chart(fig, use_container_width=True)

# Branch analysis
st.markdown('<div class="section">Branch Performance</div>', unsafe_allow_html=True)
branch_summary = (
    filtered.groupby(["Zone","Branch Name"], dropna=False)
    .agg({"Target":"sum","Sale Value":"sum","Cash":"sum","HP":"sum","YTD SV":"sum"})
    .reset_index()
)
branch_summary["Achievement %"] = branch_summary["Sale Value"] / branch_summary["Target"].replace(0, np.nan) * 100
branch_summary["Variance"] = branch_summary["Sale Value"] - branch_summary["Target"]
branch_summary = branch_summary.fillna(0).sort_values("Sale Value", ascending=False)

b1,b2 = st.columns(2)
with b1:
    top = branch_summary.head(15)
    fig = px.bar(top, x="Sale Value", y="Branch Name", orientation="h", title="Highest Value Contributors")
    fig.update_layout(yaxis={"categoryorder":"total ascending"})
    st.plotly_chart(fig, use_container_width=True)
with b2:
    bottom = branch_summary.sort_values("Achievement %").head(15)
    fig = px.bar(bottom, x="Achievement %", y="Branch Name", orientation="h", title="Branches Requiring Attention")
    fig.update_layout(yaxis={"categoryorder":"total descending"})
    st.plotly_chart(fig, use_container_width=True)

# Cash vs installment
st.markdown('<div class="section">Cash vs Installment</div>', unsafe_allow_html=True)
mix = pd.DataFrame({
    "Payment Type":["Cash","Installment"],
    "Sales":[cash_sales,hp_sales],
})
c1,c2 = st.columns(2)
with c1:
    fig = px.pie(mix, names="Payment Type", values="Sales", hole=0.55, title="Overall Payment Mix")
    st.plotly_chart(fig, use_container_width=True)
with c2:
    zone_mix = zone_summary.melt(
        id_vars="Zone",
        value_vars=["Cash","HP"],
        var_name="Payment Type",
        value_name="Sales",
    )
    fig = px.bar(zone_mix, x="Zone", y="Sales", color="Payment Type", barmode="stack", title="Payment Mix by Zone")
    st.plotly_chart(fig, use_container_width=True)

# Category/SBU analysis from raw data
if raw is not None:
    raw = clean_columns(raw)
    for c in ["SV","QTY","QTY.1","LINEAMOUNT","SALESPRICE"]:
        if c in raw.columns:
            raw[c] = pd.to_numeric(raw[c], errors="coerce").fillna(0)

    value_col = "SV" if "SV" in raw.columns else "LINEAMOUNT" if "LINEAMOUNT" in raw.columns else None
    category_col = "CAT" if "CAT" in raw.columns else "CATEGORY" if "CATEGORY" in raw.columns else None
    brand_col = "BRAND" if "BRAND" in raw.columns else None

    if value_col and category_col:
        st.markdown('<div class="section">Category Analysis</div>', unsafe_allow_html=True)
        category = raw.groupby(category_col, dropna=False)[value_col].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(category, x=category_col, y=value_col, title="Sales by Category")
        st.plotly_chart(fig, use_container_width=True)

    if value_col and brand_col:
        st.markdown('<div class="section">Brand Analysis</div>', unsafe_allow_html=True)
        brand = raw.groupby(brand_col, dropna=False)[value_col].sum().sort_values(ascending=False).head(20).reset_index()
        fig = px.bar(brand, x=brand_col, y=value_col, title="Top Brands by Sales")
        st.plotly_chart(fig, use_container_width=True)

    if date_col and value_col:
        st.markdown('<div class="section">Daily Sales Trend</div>', unsafe_allow_html=True)
        temp = raw.copy()
        temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
        daily = temp.dropna(subset=[date_col]).groupby(temp[date_col].dt.date)[value_col].sum().reset_index()
        daily.columns = ["Date","Sales"]
        fig = px.line(daily, x="Date", y="Sales", markers=True, title="Daily Sales")
        st.plotly_chart(fig, use_container_width=True)

# Conclusions
st.markdown('<div class="section">Automatic Management Conclusions</div>', unsafe_allow_html=True)
insights = []
if len(zone_summary):
    best_zone = zone_summary.sort_values("MTD Achievement %", ascending=False).iloc[0]
    worst_zone = zone_summary.sort_values("MTD Achievement %").iloc[0]
    insights.append(f"{best_zone['Zone']} is the strongest zone with {best_zone['MTD Achievement %']:.1f}% MTD achievement.")
    insights.append(f"{worst_zone['Zone']} has the lowest MTD achievement at {worst_zone['MTD Achievement %']:.1f}%.")

if len(branch_summary):
    best_branch = branch_summary.iloc[0]
    weak_branch = branch_summary.sort_values("Achievement %").iloc[0]
    insights.append(f"{best_branch['Branch Name']} is the highest value contributor with {money(best_branch['Sale Value'])}.")
    insights.append(f"{weak_branch['Branch Name']} requires attention with {weak_branch['Achievement %']:.1f}% achievement.")

insights.append(f"Current run rate is {money(current_run_rate)} versus the required rate of {money(required_run_rate)}.")
insights.append(f"Cash achievement is {cash_ach*100:.1f}% and installment achievement is {hp_ach*100:.1f}%.")

for item in insights:
    st.markdown(f'<div class="insight">{item}</div>', unsafe_allow_html=True)

# Excel-style table and downloads
st.markdown('<div class="section">Detailed Data</div>', unsafe_allow_html=True)
gb = GridOptionsBuilder.from_dataframe(filtered)
gb.configure_default_column(sortable=True, filter=True, resizable=True, floatingFilter=True)
gb.configure_pagination(enabled=True, paginationPageSize=50)
gb.configure_side_bar()
AgGrid(filtered, gridOptions=gb.build(), height=550, theme="streamlit")

d1,d2 = st.columns(2)
d1.download_button(
    "Download Branch Analysis",
    excel_bytes(branch_summary, "Branch Analysis"),
    "branch_analysis.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
d2.download_button(
    "Download Zone Analysis",
    excel_bytes(zone_summary, "Zone Analysis"),
    "zone_analysis.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

st.caption("This version is optimized for the reporting workbook structure used by your department.")
