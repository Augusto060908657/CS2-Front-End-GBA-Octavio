"""
frontend/app.py — Página inicial: LEITURA ATUAL
Consome  GET /v1/sensores/{tag}/leitura-atual  (X-Feature: dashboard-leitura-atual)
"""
import pandas as pd
import streamlit as st

from common import bloco_simulacao, mostrar_requisicao, para_local, preparar_pagina, selecionar_sensor, sidebar_base
from theme import ROTULOS, pill

preparar_pagina("Leitura Atual", "📡")
cliente = sidebar_base()
sel = selecionar_sensor(cliente)
if not sel:
    st.title("📡 Leitura Atual")
    st.warning("Inicie a API (`uvicorn backend.main:app --port 8000`) e recarregue esta página.")
    st.stop()
sensor, catalogo = sel
sim = bloco_simulacao("leitura")

with st.sidebar:
    st.button("🔄 Atualizar agora", width="stretch", type="primary")
    auto = st.toggle("⏱️ Atualização automática", value=False)
    intervalo = st.selectbox("Intervalo", [5, 10, 20, 30, 60], index=1, format_func=lambda s: f"{s} s", disabled=not auto)
    st.divider()


@st.fragment(run_every=intervalo if auto else None)
def painel():
    st.title(f"📡 {sensor['tag']} — {sensor['nome']}")
    st.caption(f"{sensor['planta']} · {sensor['linha']}  •  {sensor['modelo']}  •  {sensor['potencia']}")

    r = cliente.leitura_atual(sensor["tag"], feature="dashboard-leitura-atual", **sim)
    mostrar_requisicao(r)
    if not r.ok:
        st.error(f"A API respondeu com erro: {r.erro}")
        return
    d, L, lim = r.data, r.data["leituras"], r.data["limites"]

    c1, c2 = st.columns([3, 2])
    c1.markdown(f"**Severidade retornada pela API:** {pill(d['severidade'])} &nbsp; (métrica mais próxima do limite: "
                f"**{d['metrica_critica']}**)", unsafe_allow_html=True)
    medicao = para_local(pd.Series([d["timestamp_medicao"]])).iloc[0]
    rotulo_fresh = f"{d['freshness_s']:.0f} s"
    c2.markdown(f"**Freshness:** {pill(d['freshness_status'], rotulo_fresh)} &nbsp; "
                f"medido em {medicao:%d/%m %H:%M:%S}", unsafe_allow_html=True)
    if d["freshness_status"] != "ok":
        st.warning(f"⚠ Dado com {d['freshness_s']:.0f}s de idade — acima do SLA de atualização. "
                   "Esta ocorrência está sendo registrada na observabilidade.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🌡 Temperatura", f"{L['temperatura_c']} °C", f"{L['temperatura_c'] - lim['temperatura_c']:+.1f} °C vs limite", delta_color="inverse")
    k2.metric("📳 Vibração", f"{L['vibracao_mm_s']} mm/s", f"{L['vibracao_mm_s'] - lim['vibracao_mm_s']:+.2f} vs limite", delta_color="inverse")
    k3.metric("⚡ Corrente", f"{L['corrente_a']} A", f"{L['corrente_a'] - lim['corrente_a']:+.1f} A vs limite", delta_color="inverse")
    k4.metric("🔄 Velocidade", f"{L['rpm']} RPM")

    st.divider()
    st.markdown("#### 🗺️ Visão geral de todos os sensores")
    linhas = []
    for item in catalogo:
        rr = cliente.leitura_atual(item["tag"], feature="dashboard-visao-geral")
        if rr.ok:
            x = rr.data
            linhas.append({"TAG": x["tag"], "Equipamento": x["nome"], "Planta / Linha": f"{x['planta']} · {x['linha']}",
                           "Severidade": ROTULOS[x["severidade"]][0], "Temp. (°C)": x["leituras"]["temperatura_c"],
                           "Vib. (mm/s)": x["leituras"]["vibracao_mm_s"], "Corrente (A)": x["leituras"]["corrente_a"],
                           "Freshness (s)": x["freshness_s"], "SLA": ROTULOS[x["freshness_status"]][0]})
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    st.caption("Cada leitura acima é uma chamada à API e gera um registro de observabilidade "
               "(`X-Feature: dashboard-visao-geral`).")


painel()
