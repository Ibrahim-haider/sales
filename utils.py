
from __future__ import annotations

import io
import re
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd


ALIASES: Dict[str, List[str]] = {
    "branch": ["branch", "branch name", "store", "store name", "outlet", "location"],
    "zone": ["zone", "region", "area", "territory"],
    "target": ["target", "sales target", "mtd target", "monthly target"],
    "sales": ["sales", "sale value", "sales value", "actual sales", "net sales", "mtd sales", "sv"],
    "cash_sales": ["cash", "cash sales", "cash sale value", "cash sv"],
    "installment_sales": ["installment", "installments", "hp", "hire purchase", "installment sales"],
    "ytd_sales": ["ytd sales", "year to date sales", "ytd sv"],
    "ytd_target": ["ytd target", "year to date target", "ytd tgt"],
    "date": ["date", "transaction date", "sales date", "invoice date"],
    "quantity": ["qty", "quantity", "units", "units sold"],
    "category": ["category", "product category", "segment"],
    "product": ["product", "item", "sku", "product name"],
}


def normalize_name(name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name).strip().lower()).strip()


def infer_mapping(columns: Iterable[str]) -> Dict[str, str | None]:
    normalized = {normalize_name(c): c for c in columns}
    result: Dict[str, str | None] = {}
    for canonical, aliases in ALIASES.items():
        found = None
        candidates = [canonical.replace("_", " ")] + aliases
        for alias in candidates:
            key = normalize_name(alias)
            if key in normalized:
                found = normalized[key]
                break
        if found is None:
            for col in columns:
                ncol = normalize_name(col)
                if any(normalize_name(a) in ncol or ncol in normalize_name(a) for a in candidates):
                    found = col
                    break
        result[canonical] = found
    return result


def json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.to_datetime(value).isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return None
    if pd.isna(value):
        return None
    return value


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(k): json_safe_value(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def detect_column_types(df: pd.DataFrame) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            result[str(col)] = "date"
            continue
        numeric = pd.to_numeric(s, errors="coerce")
        if len(s) and numeric.notna().mean() >= 0.8:
            result[str(col)] = "number"
            continue
        unique_count = s.nunique(dropna=True)
        if unique_count <= 50:
            result[str(col)] = "category"
        else:
            result[str(col)] = "text"
    return result


def apply_filters(df: pd.DataFrame, rules: list[Any]) -> pd.DataFrame:
    out = df.copy()
    for rule in rules:
        col = rule.column
        if col not in out.columns:
            continue
        op = rule.operator
        value = rule.value
        value2 = rule.value2
        s = out[col]

        if op == "equals":
            out = out[s.astype(str) == str(value)]
        elif op == "not_equals":
            out = out[s.astype(str) != str(value)]
        elif op == "contains":
            out = out[s.astype(str).str.contains(str(value), case=False, na=False)]
        elif op == "not_contains":
            out = out[~s.astype(str).str.contains(str(value), case=False, na=False)]
        elif op == "in":
            values = value if isinstance(value, list) else [value]
            out = out[s.astype(str).isin([str(v) for v in values])]
        elif op in {"gt", "gte", "lt", "lte", "between"}:
            numeric = pd.to_numeric(s, errors="coerce")
            if op == "gt":
                out = out[numeric > float(value)]
            elif op == "gte":
                out = out[numeric >= float(value)]
            elif op == "lt":
                out = out[numeric < float(value)]
            elif op == "lte":
                out = out[numeric <= float(value)]
            elif op == "between":
                out = out[numeric.between(float(value), float(value2))]
        elif op in {"date_before", "date_after", "date_between"}:
            dates = pd.to_datetime(s, errors="coerce")
            if op == "date_before":
                out = out[dates < pd.to_datetime(value)]
            elif op == "date_after":
                out = out[dates > pd.to_datetime(value)]
            else:
                out = out[dates.between(pd.to_datetime(value), pd.to_datetime(value2))]
        elif op == "is_blank":
            out = out[s.isna() | (s.astype(str).str.strip() == "")]
        elif op == "is_not_blank":
            out = out[~(s.isna() | (s.astype(str).str.strip() == ""))]
    return out


SAFE_FUNCTIONS = {
    "abs": np.abs,
    "round": np.round,
    "sqrt": np.sqrt,
    "log": np.log,
    "exp": np.exp,
}


def add_calculated_column(df: pd.DataFrame, name: str, expression: str) -> pd.DataFrame:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_ ]*$", name):
        raise ValueError("Column name contains unsupported characters.")

    if "__" in expression or "import" in expression.lower():
        raise ValueError("Unsafe expression.")

    local_dict = {str(c): pd.to_numeric(df[c], errors="coerce") for c in df.columns}
    local_dict.update(SAFE_FUNCTIONS)

    try:
        result = pd.eval(expression, local_dict=local_dict, engine="python")
    except Exception as exc:
        raise ValueError(f"Invalid expression: {exc}") from exc

    out = df.copy()
    out[name] = result
    return out
