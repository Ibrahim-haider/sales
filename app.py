
from __future__ import annotations

import io
import json
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(page_title="Universal Excel Analytics", page_icon="📊", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:1rem}
.hero{padding:22px 24px;border-radius:18px;background:linear-gradient(135deg,#10284d,#2563eb);color:white;margin-bottom:18px}
.hero h1{margin:0 0 6px}.hero p{margin:0;opacity:.9}
</style>
<div class="hero"><h1>Universal Excel Analytics</h1>
<p>Upload, map, filter, clean, calculate, analyse, visualize and export structured business data.</p></div>
""", unsafe_allow_html=True)

ALIASES = {
    "branch":["branch","branch name","store","outlet","location"],
    "zone":["zone","region","area","territory"],
    "target":["target","sales target","mtd target","monthly target"],
    "sales":["sales","sale value","sales value","actual sales","net sales","mtd sales","sv"],
    "cash_sales":["cash","cash sales","cash sv"],
    "installment_sales":["installment","installments","hp","hire purchase"],
    "ytd_sales":["ytd sales","year to date sales","ytd sv"],
    "ytd_target":["ytd target","year to date target","ytd tgt"],
    "date":["date","transaction date","sales date","invoice date"],
    "quantity":["qty","quantity","units","units sold"],
    "category":["category","product category","segment"],
    "product":["product","item","sku","product name"],
}

def norm(v):
    return re.sub(r"[^a-z0-9]+"," ",str(v).lower()).strip()

def infer_mapping(columns):
    normalized={norm(c):str(c) for c in columns}
    result={}
    for canonical,aliases in ALIASES.items():
        found=None
        for alias in [canonical.replace("_"," ")]+aliases:
            if norm(alias) in normalized:
                found=normalized[norm(alias)]
                break
        result[canonical]=found
    return result

def parse_file(uploaded):
    raw=uploaded.getvalue()
    name=uploaded.name.lower()
    if name.endswith(".csv"):
        return {"Data":pd.read_csv(io.BytesIO(raw))}
    xls=pd.ExcelFile(io.BytesIO(raw))
    return {s:pd.read_excel(io.BytesIO(raw),sheet_name=s) for s in xls.sheet_names}

def to_excel_bytes(sheets):
    bio=io.BytesIO()
    with pd.ExcelWriter(bio,engine="openpyxl") as writer:
        for name,frame in sheets.items():
            frame.to_excel(writer,index=False,sheet_name=re.sub(r'[\[\]\*\?/\\:]','_',name)[:31] or "Sheet1")
    return bio.getvalue()

def numeric_cols(df):
    return [c for c in df.columns if pd.to_numeric(df[c],errors="coerce").notna().mean()>=.8]

def safe_formula(df,expr):
    if "__" in expr or "import" in expr.lower():
        raise ValueError("Unsafe expression")
    local={str(c):pd.to_numeric(df[c],errors="coerce") for c in df.columns}
    local.update({"abs":np.abs,"round":np.round,"sqrt":np.sqrt,"log":np.log,"exp":np.exp})
    return pd.eval(expr,local_dict=local,engine="python")

if "sheets" not in st.session_state: st.session_state.sheets={}
if "active_sheet" not in st.session_state: st.session_state.active_sheet=None
if "mapping" not in st.session_state: st.session_state.mapping={}
if "filtered" not in st.session_state: st.session_state.filtered=None
if "last_file" not in st.session_state: st.session_state.last_file=None
if "templates" not in st.session_state: st.session_state.templates={}

with st.sidebar:
    st.header("Workspace")
    uploaded=st.file_uploader("Upload Excel or CSV",type=["xlsx","xls","csv"])
    if uploaded is not None:
        key=f"{uploaded.name}_{uploaded.size}"
        if key!=st.session_state.last_file:
            try:
                st.session_state.sheets=parse_file(uploaded)
                st.session_state.active_sheet=next(iter(st.session_state.sheets))
                st.session_state.mapping=infer_mapping(st.session_state.sheets[st.session_state.active_sheet].columns)
                st.session_state.filtered=None
                st.session_state.last_file=key
                st.success("File loaded")
            except Exception as exc:
                st.error(str(exc))
    if st.session_state.sheets:
        names=list(st.session_state.sheets)
        selected=st.selectbox("Sheet",names,index=names.index(st.session_state.active_sheet))
        if selected!=st.session_state.active_sheet:
            st.session_state.active_sheet=selected
            st.session_state.mapping=infer_mapping(st.session_state.sheets[selected].columns)
            st.session_state.filtered=None
            st.rerun()
        page=st.radio("Go to",[
            "Data Workspace","Column Mapping","Data Cleaning",
            "Calculated Columns","Analysis & Pivot","Charts","Templates & Export"
        ])
    else:
        page=None

if not st.session_state.sheets:
    st.info("Upload a structured Excel or CSV file to begin.")
    st.stop()

df=st.session_state.sheets[st.session_state.active_sheet].copy()

if page=="Data Workspace":
    st.header("Data Workspace")
    a,b,c,d=st.columns(4)
    a.metric("Rows",f"{len(df):,}")
    b.metric("Columns",len(df.columns))
    c.metric("Missing cells",f"{int(df.isna().sum().sum()):,}")
    d.metric("Duplicates",f"{int(df.duplicated().sum()):,}")

    with st.expander("Advanced Excel-style filters"):
        filtered=df.copy()
        for i,col in enumerate(df.columns):
            s=filtered[col]
            num=pd.to_numeric(s,errors="coerce")
            if len(s) and num.notna().mean()>=.8 and num.notna().any():
                lo,hi=float(num.min()),float(num.max())
                if lo!=hi:
                    chosen=st.slider(str(col),lo,hi,(lo,hi),key=f"n_{i}_{col}")
                    filtered=filtered[pd.to_numeric(filtered[col],errors="coerce").between(*chosen)]
            elif s.nunique(dropna=True)<=50:
                opts=sorted(s.dropna().astype(str).unique().tolist())
                selected=st.multiselect(str(col),opts,default=opts,key=f"c_{i}_{col}")
                filtered=filtered[filtered[col].astype(str).isin(selected)] if selected else filtered.iloc[0:0]
            else:
                q=st.text_input(f"{col} contains",key=f"t_{i}_{col}")
                if q: filtered=filtered[filtered[col].astype(str).str.contains(q,case=False,na=False)]
    st.session_state.filtered=filtered

    gb=GridOptionsBuilder.from_dataframe(filtered)
    gb.configure_default_column(sortable=True,filter=True,resizable=True,floatingFilter=True)
    gb.configure_pagination(enabled=True,paginationPageSize=50)
    gb.configure_side_bar()
    AgGrid(filtered,gridOptions=gb.build(),height=600,theme="streamlit")

elif page=="Column Mapping":
    st.header("Column Mapping")
    columns=["— Not mapped —"]+[str(c) for c in df.columns]
    mapping=st.session_state.mapping.copy()
    left,right=st.columns(2)
    for i,key in enumerate(ALIASES):
        current=mapping.get(key)
        index=columns.index(current) if current in columns else 0
        with (left if i%2==0 else right):
            choice=st.selectbox(key.replace("_"," ").title(),columns,index=index,key=f"map_{key}")
            mapping[key]=None if choice=="— Not mapped —" else choice
    if st.button("Save mapping",type="primary"):
        st.session_state.mapping=mapping
        st.success("Mapping saved")
    st.json(mapping)

elif page=="Data Cleaning":
    st.header("Data Cleaning")
    c1,c2,c3=st.columns(3)
    drop_dupes=c1.checkbox("Remove duplicate rows")
    drop_blank_rows=c2.checkbox("Remove blank rows")
    drop_blank_cols=c3.checkbox("Remove blank columns")
    rename_source=st.selectbox("Rename column",["— None —"]+list(df.columns))
    rename_target=st.text_input("New name")
    remove_cols=st.multiselect("Remove columns",list(df.columns))
    if st.button("Apply cleaning",type="primary"):
        out=df.copy()
        if drop_dupes: out=out.drop_duplicates()
        if drop_blank_rows: out=out.dropna(how="all")
        if drop_blank_cols: out=out.dropna(axis=1,how="all")
        if rename_source!="— None —" and rename_target.strip():
            out=out.rename(columns={rename_source:rename_target.strip()})
        if remove_cols: out=out.drop(columns=remove_cols,errors="ignore")
        st.session_state.sheets[st.session_state.active_sheet]=out
        st.session_state.filtered=None
        st.rerun()
    st.dataframe(df.head(100),use_container_width=True)

elif page=="Calculated Columns":
    st.header("Calculated Columns")
    st.caption("Example: Sales / Target * 100")
    name=st.text_input("New column name")
    expr=st.text_input("Expression")
    if st.button("Create column",type="primary"):
        try:
            out=df.copy()
            out[name.strip()]=safe_formula(out,expr.strip())
            st.session_state.sheets[st.session_state.active_sheet]=out
            st.session_state.filtered=None
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.dataframe(df.head(100),use_container_width=True)

elif page=="Analysis & Pivot":
    st.header("Analysis & Pivot")
    group=st.multiselect("Group by",list(df.columns))
    metric=st.selectbox("Metric",list(df.columns))
    operation=st.selectbox("Aggregation",["sum","mean","count","min","max","median","nunique"])
    if st.button("Run analysis",type="primary"):
        try:
            if group:
                result=df.groupby(group,dropna=False)[metric].agg(operation).reset_index(name=f"{operation}_{metric}")
            else:
                s=df[metric]
                value=s.nunique() if operation=="nunique" else getattr(s,operation)()
                result=pd.DataFrame([{f"{operation}_{metric}":value}])
            st.session_state.analysis=result
        except Exception as exc:
            st.error(str(exc))
    if "analysis" in st.session_state:
        st.dataframe(st.session_state.analysis,use_container_width=True)

elif page=="Charts":
    st.header("Charts")
    nums=numeric_cols(df)
    if not nums:
        st.warning("No numeric columns detected.")
    else:
        c1,c2,c3,c4=st.columns(4)
        chart=c1.selectbox("Chart",["Bar","Line","Pie","Scatter","Histogram"])
        x=c2.selectbox("X / category",list(df.columns))
        y=c3.selectbox("Y / value",nums)
        agg=c4.selectbox("Aggregation",["sum","mean","count","min","max"])
        if st.button("Generate chart",type="primary"):
            try:
                if chart=="Histogram":
                    fig=px.histogram(df,x=y)
                elif chart=="Scatter":
                    fig=px.scatter(df,x=x,y=y)
                else:
                    g=df.groupby(x,dropna=False)[y].agg(agg).reset_index()
                    fig=px.bar(g,x=x,y=y) if chart=="Bar" else px.line(g,x=x,y=y,markers=True) if chart=="Line" else px.pie(g,names=x,values=y,hole=.45)
                st.plotly_chart(fig,use_container_width=True)
            except Exception as exc:
                st.error(str(exc))

elif page=="Templates & Export":
    st.header("Templates & Export")
    template_name=st.text_input("Template name")
    if st.button("Save mapping template"):
        if template_name.strip():
            st.session_state.templates[template_name.strip()]={"sheet":st.session_state.active_sheet,"mapping":st.session_state.mapping}
            st.success("Template saved for this session")
    if st.session_state.templates:
        selected=st.selectbox("Saved templates",list(st.session_state.templates))
        st.download_button("Download template",json.dumps(st.session_state.templates[selected],indent=2).encode(),"template.json","application/json")

    export_df=st.session_state.filtered if st.session_state.filtered is not None else df
    c1,c2,c3=st.columns(3)
    c1.download_button("Download CSV",export_df.to_csv(index=False).encode(),"filtered_data.csv","text/csv",use_container_width=True)
    c2.download_button("Download Excel",to_excel_bytes({"Filtered Data":export_df}),"filtered_data.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
    c3.download_button("Download all sheets",to_excel_bytes(st.session_state.sheets),"processed_workbook.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)

st.divider()
st.caption("Internal analytics prototype • Structured Excel/CSV only • No VBA or macros")
