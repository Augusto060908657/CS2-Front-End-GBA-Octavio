"""
frontend/pages/2_Observabilidade.py — RELATÓRIO DE OBSERVABILIDADE
Consome  GET /v1/observabilidade  e  GET /v1/observabilidade/indicadores
(X-Feature: dashboard-observabilidade). Evidência para a disciplina de Governança em IA.
"""
import pandas as pd
import streamlit as st

import charts
from api_client import gerar_trafego_demo
from common import mostrar_requisicao, para_local, preparar_pagina, sidebar_base
from theme import ROTULOS, pill

preparar_pagina("Observabilidade", "🛰️")
cliente = sidebar_base()

with st.sidebar:
    janela = st.selectbox("Janela de análise", [15, 60, 360, 1440, 10080], index=1,
                          format_func=lambda m: f"{m} min" if m < 60 else f"{m // 60} h" if m < 1440 else f"{m // 1440} dia(s)")
    bucket = st.selectbox("Agrupamento das séries", [30, 60, 300, 900], index=1, format_func=lambda s: f"{s} s" if s < 60 else f"{s // 60} min")
    excluir_sim = st.checkbox("Ignorar chamadas com falha injetada", False)
    st.button("🔄 Atualizar", width="stretch", type="primary")
    if st.button("🧪 Gerar tráfego de demonstração", width="stretch",
                 help="Dispara ~27 chamadas (3 sessões, várias funcionalidades, 1 sem headers, 1 TAG inválida, 1 com atraso injetado)."):
        with st.spinner("Chamando a API..."):
            res = gerar_trafego_demo(st.session_state["api_url"])
        st.success(f"{sum(r.ok for r in res)}/{len(res)} chamadas bem-sucedidas (as demais são propositais).")
    st.divider()

st.title("🛰️ Observabilidade do Endpoint de Sensores")
st.caption("Registros coletados pelo back-end a cada chamada (headers de contexto, timestamp e latência) "
           "e indicadores do contrato de métricas. Fonte: `/v1/observabilidade`.")

ri = cliente.indicadores(janela_min=janela, bucket_s=bucket, excluir_simulacoes=excluir_sim)
rr = cliente.observabilidade(limite=2000)
if not ri.ok or not rr.ok:
    st.error(f"Não foi possível consultar a API: {ri.erro or rr.erro}")
    st.stop()
mostrar_requisicao(ri)
ind, regs = ri.data, rr.data

if ind["total_chamadas"] == 0:
    st.info("Ainda não há chamadas de dados na janela escolhida. Navegue pelas páginas **Leitura Atual** e "
            "**Histórico** ou clique em **Gerar tráfego de demonstração** na barra lateral.")

por_id = {i["id"]: i for i in ind["indicadores"]}
res = ind["resumo"]

# ── KPIs ────────────────────────────────────────────
k = st.columns(5)
k[0].metric("Chamadas (dados)", ind["total_chamadas"])
k[1].metric("Taxa de sucesso (2xx)", "—" if res["sucesso_pct"] is None else f"{res['sucesso_pct']:.1f} %")
k[2].metric("Latência p50 / p95", "—" if res["latencia_ms"]["p50"] is None else f"{res['latencia_ms']['p50']:.0f} / {res['latencia_ms']['p95']:.0f} ms")
k[3].metric("Sessões distintas", res["sessoes_distintas"])
k[4].metric("Registros totais no banco", regs["total"])

aba_i, aba_g, aba_r = st.tabs(["📋 Contrato de métricas", "📊 Gráficos por indicador", "🗂️ Registros brutos"])

# ── Contrato ────────────────────────────────────────
with aba_i:
    st.markdown("Cada indicador tem **baseline**, **limiares** e uma **ação** definida para quando o limiar for estourado.")
    linhas = []
    for i in ind["indicadores"]:
        sinal = "<" if i["direcao"] == "min" else ">"
        linhas.append({
            "Indicador": i["nome"], "Valor atual": "—" if i["valor"] is None else f"{i['valor']:g} {i['unidade']}",
            "Status": ROTULOS[i["status"]][0], "Baseline": f"{i['baseline']:g} {i['unidade']}",
            "Atenção": f"{sinal} {i['atencao']:g}", "Crítico": f"{sinal} {i['critico']:g}", "Amostra": i["amostra"],
        })
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

    for i in ind["indicadores"]:
        with st.expander(f"{ROTULOS[i['status']][0].split()[0]}  {i['nome']}"):
            st.markdown(f"**Definição:** {i['descricao']}")
            st.markdown(f"**Fórmula:** `{i['formula']}`")
            st.markdown(f"**Camada gráfica:** {i['grafico']}")
            st.markdown(f"**Ação ao estourar (atenção):** {i['acao_atencao']}")
            st.markdown(f"**Ação ao estourar (crítico):** {i['acao_critico']}")
            st.markdown(f"**Ação recomendada agora:** {i['acao_recomendada']}")

# ── Gráficos ────────────────────────────────────────
with aba_g:
    if not regs["registros"]:
        st.info("Sem registros para exibir.")
    else:
        df = pd.DataFrame(regs["registros"])
        df["timestamp"] = para_local(df["timestamp"])
        df = df.sort_values("timestamp")
        dados = df[df["endpoint"].str.startswith("/v1/sensores", na=False)]
        sdf = pd.DataFrame(ind["series"])
        if not sdf.empty:
            sdf["bucket"] = para_local(sdf["bucket"])

        c1, c2 = st.columns(2)
        with c1:
            f = dados[dados["freshness_s"].notna()]
            st.plotly_chart(charts.linha_limiar(f, "timestamp", "freshness_s", "Freshness por chamada de leitura (s)",
                                                por_id["freshness_p95_s"], "Freshness", markers=True), width="stretch")
            st.caption(f"Indicador: {por_id['freshness_p95_s']['nome']} → {pill(por_id['freshness_p95_s']['status'])}", unsafe_allow_html=True)
        with c2:
            if not sdf.empty and sdf["freshness_ok_pct"].notna().any():
                st.plotly_chart(charts.linha_limiar(sdf[sdf["freshness_ok_pct"].notna()], "bucket", "freshness_ok_pct",
                                                    "Taxa de completude de Freshness (%)", por_id["taxa_freshness_ok"], "Taxa", markers=True),
                                width="stretch")
            else:
                st.info("Sem leituras na janela para calcular a taxa de Freshness.")
            st.caption(f"Indicador: {por_id['taxa_freshness_ok']['nome']} → {pill(por_id['taxa_freshness_ok']['status'])}", unsafe_allow_html=True)

        c3, c4 = st.columns(2)
        with c3:
            h = dados[dados["completude_pct"].notna()]
            if not h.empty:
                st.plotly_chart(charts.linha_limiar(h, "timestamp", "completude_pct", "Completude do histórico por consulta (%)",
                                                    por_id["completude_historico"], "Completude", markers=True), width="stretch")
            else:
                st.info("Nenhuma consulta de histórico na janela.")
            st.caption(f"Indicador: {por_id['completude_historico']['nome']} → {pill(por_id['completude_historico']['status'])}", unsafe_allow_html=True)
        with c4:
            st.plotly_chart(charts.linha_limiar(dados, "timestamp", "latencia_ms", "Latência por chamada (ms)",
                                                por_id["latencia_p95_ms"], "Latência", markers=True), width="stretch")
            st.caption(f"Indicador: {por_id['latencia_p95_ms']['nome']} → {pill(por_id['latencia_p95_ms']['status'])}", unsafe_allow_html=True)

        c5, c6 = st.columns(2)
        with c5:
            if not sdf.empty:
                st.plotly_chart(charts.barras_status(sdf), width="stretch")
            st.caption(f"Indicador: {por_id['taxa_erro_5xx']['nome']} → {pill(por_id['taxa_erro_5xx']['status'])}", unsafe_allow_html=True)
        with c6:
            conf = por_id["conformidade_headers"]
            st.plotly_chart(charts.gauge(conf["valor"], conf, "Conformidade dos headers"), width="stretch")
            st.caption(f"Indicador: {conf['nome']} → {pill(conf['status'])}", unsafe_allow_html=True)

        c7, c8 = st.columns(2)
        with c7:
            if res["por_feature"]:
                st.plotly_chart(charts.barras_categoria(res["por_feature"], "Chamadas por funcionalidade (X-Feature)"), width="stretch")
        with c8:
            if res["por_endpoint"]:
                st.plotly_chart(charts.barras_categoria(res["por_endpoint"], "Chamadas por endpoint"), width="stretch")

# ── Registros ───────────────────────────────────────
with aba_r:
    df = pd.DataFrame(regs["registros"])
    if df.empty:
        st.info("Nenhum registro coletado ainda.")
    else:
        df["timestamp"] = para_local(df["timestamp"])
        f1, f2, f3, f4 = st.columns(4)
        feat = f1.selectbox("Funcionalidade", ["(todas)"] + sorted(df["feature"].dropna().unique().tolist()))
        ep = f2.selectbox("Endpoint", ["(todos)"] + sorted(df["endpoint"].dropna().unique().tolist()))
        stt = f3.selectbox("Status HTTP", ["(todos)"] + sorted(df["status_code"].unique().tolist()))
        so_sem_ctx = f4.checkbox("Só sem headers de contexto", False)
        if feat != "(todas)":
            df = df[df["feature"] == feat]
        if ep != "(todos)":
            df = df[df["endpoint"] == ep]
        if stt != "(todos)":
            df = df[df["status_code"] == stt]
        if so_sem_ctx:
            df = df[~df["contexto_completo"]]
        exibir = df[["timestamp", "session_id", "feature", "metodo", "endpoint", "tag", "status_code", "latencia_ms",
                     "freshness_s", "completude_pct", "severidade", "contexto_completo", "simulacao", "request_id"]]
        st.caption(f"{len(exibir)} de {regs['total']} registros (mais recentes primeiro).")
        st.dataframe(exibir, hide_index=True, width="stretch", height=420)
        st.download_button("⬇️ Baixar registros (CSV)", exibir.to_csv(index=False).encode("utf-8"),
                           file_name="observabilidade.csv", mime="text/csv")
