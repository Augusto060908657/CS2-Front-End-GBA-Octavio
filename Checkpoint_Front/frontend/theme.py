"""frontend/theme.py — estilo complementar (o tema escuro base vem de .streamlit/config.toml)."""
import streamlit as st

CSS = """
<style>
    [data-testid="stMetric"] { background:#1E2233; border:1px solid #252A3D; border-radius:8px; padding:12px 14px; }
    .pill { display:inline-block; padding:3px 12px; border-radius:20px; font-size:12px; font-weight:600; }
    .pill-ok   { background:rgba(34,197,94,.15);  color:#4ADE80; }
    .pill-warn { background:rgba(245,158,11,.15); color:#FBBF24; }
    .pill-crit { background:rgba(239,68,68,.15);  color:#F87171; }
    .pill-none { background:rgba(148,163,184,.15); color:#CBD5E1; }
    .sim-badge { background:rgba(59,130,246,.15); color:#60A5FA; padding:4px 12px; border-radius:20px;
                 font-size:12px; border:1px solid rgba(59,130,246,.3); display:inline-block; }
    .req-box { background:#161923; border:1px dashed #3B4260; border-radius:8px; padding:8px 12px;
               font-family:'Courier New',monospace; font-size:12px; color:#93C5FD; }
    .card { background:#1E2233; border:1px solid #252A3D; border-radius:10px; padding:14px 16px; }
</style>
"""

ROTULOS = {"ok": ("🟢 Saudável", "pill-ok"), "warn": ("🟡 Atenção", "pill-warn"),
           "crit": ("🔴 Crítico", "pill-crit"), "sem_dados": ("⚪ Sem dados", "pill-none")}


def aplicar_tema():
    st.markdown(CSS, unsafe_allow_html=True)


def pill(status: str, texto: str | None = None) -> str:
    rotulo, css = ROTULOS.get(status, ROTULOS["sem_dados"])
    return f'<span class="pill {css}">{texto or rotulo}</span>'
