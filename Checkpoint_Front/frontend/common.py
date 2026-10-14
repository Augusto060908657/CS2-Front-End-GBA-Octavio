"""frontend/common.py — sessão, sidebar e seleção de sensor compartilhados entre as páginas."""
import os
import time
import uuid

import pandas as pd
import streamlit as st

from api_client import ApiClient
from theme import aplicar_tema

API_PADRAO = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
FUSO = "America/Sao_Paulo"


def preparar_pagina(titulo: str, icone: str):
    st.set_page_config(layout="wide", page_title=f"{titulo} — Forzy Sensores", page_icon=icone)
    aplicar_tema()


def obter_cliente() -> ApiClient:
    ss = st.session_state
    ss.setdefault("session_id", f"st-{uuid.uuid4().hex[:10]}")   # vira o header X-Session-Id
    ss.setdefault("api_url", API_PADRAO)
    return ApiClient(ss["api_url"], ss["session_id"])


def para_local(serie) -> pd.Series:
    """Converte timestamps UTC da API para o horário de Brasília."""
    return pd.to_datetime(serie, utc=True).dt.tz_convert(FUSO).dt.tz_localize(None)


def sidebar_base() -> ApiClient:
    """Bloco comum: URL da API, status da conexão e id da sessão."""
    cliente = obter_cliente()
    with st.sidebar:
        st.markdown("## 📡 Forzy · Sensores")
        st.markdown('<span class="sim-badge">⚠ Dados simulados</span>', unsafe_allow_html=True)
        st.text_input("URL da API", key="api_url", help="Padrão: http://127.0.0.1:8000")
        h = cliente.health()
        if h.ok:
            st.success("API online", icon="✅")
        else:
            st.error("API offline — inicie o back-end (veja o README).", icon="🚫")
        st.caption(f"X-Session-Id: `{cliente.session_id}`")
        st.divider()
    return cliente


def selecionar_sensor(cliente: ApiClient):
    """Seleção em 3 níveis (Planta -> Linha/Área -> TAG) alimentada pelo catálogo da API.
    Retorna (sensor_selecionado, catalogo_completo) ou None se a API estiver indisponível."""
    ss = st.session_state
    cache = ss.get("_catalogo")
    if not cache or time.time() - cache["t"] > 120 or cache["url"] != ss["api_url"]:
        r = cliente.sensores()
        if not r.ok:
            st.error(f"Não foi possível carregar o catálogo de sensores: {r.erro}")
            return None
        cache = ss["_catalogo"] = {"t": time.time(), "url": ss["api_url"], "itens": r.data["sensores"]}
    itens = cache["itens"]

    with st.sidebar:
        plantas = sorted({i["planta"] for i in itens})
        planta = st.selectbox("🏭 Planta", plantas, key="sel_planta")
        linhas = sorted({i["linha"] for i in itens if i["planta"] == planta})
        linha = st.selectbox("📍 Linha / Área", linhas, key="sel_linha")
        tags = [i for i in itens if i["planta"] == planta and i["linha"] == linha]
        tag = st.radio("Equipamento (TAG)", [t["tag"] for t in tags], key="sel_tag",
                       format_func=lambda x: f"{x} — {next(t['nome'] for t in tags if t['tag'] == x)}")
    return next(t for t in tags if t["tag"] == tag), itens


def bloco_simulacao(tipo: str) -> dict:
    """Controles da injeção de falhas (demonstração dos limiares do contrato)."""
    sim = {}
    with st.sidebar.expander("🧪 Injeção de falhas (demo)"):
        st.caption("Força situações de estouro de limiar para evidenciar os indicadores de Governança.")
        if tipo == "leitura":
            sim["simular_atraso_s"] = st.slider("Atraso extra do sensor (s)", 0, 900, 0, 30)
        else:
            sim["simular_falhas"] = st.slider("Pontos perdidos extras", 0.0, 0.5, 0.0, 0.05)
        sim["simular_latencia_ms"] = st.slider("Latência extra da API (ms)", 0, 1500, 0, 100)
        sim["simular_erro"] = st.checkbox("Forçar erro HTTP 500", False)
    return sim


def mostrar_requisicao(r):
    st.markdown(f'<div class="req-box">🔗 {r.resumo()}</div>', unsafe_allow_html=True)
