from __future__ import annotations

import pandas as pd
import streamlit as st


def risk_badge(level: str) -> str:
    level = (level or "").upper()
    if level == "HIGH":
        return "🔴 HIGH"
    if level == "MEDIUM":
        return "🟠 MEDIUM"
    return "🟢 LOW"


def risk_color(level: str) -> str:
    level = (level or "").upper()
    if level == "HIGH":
        return "#DC2626"  # red
    if level == "MEDIUM":
        return "#F59E0B"  # amber
    return "#16A34A"  # green


def safe_upper(s: object) -> str:
    return str(s).upper() if s is not None else ""


def df_to_csv_download(df: pd.DataFrame, label: str, file_name: str) -> None:
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
    )


def kpi_card(label: str, value: object, delta: object | None = None, help_text: str | None = None) -> None:
    st.metric(label=label, value=value, delta=delta, help=help_text)
