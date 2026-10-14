"""
frontend/pages/1_Historico.py — HISTÓRICO
Consome  GET /v1/sensores/{tag}/historico  (X-Feature: dashboard-historico)
"""
import pandas as pd
import streamlit as st

from charts import serie_historico
from common import bloco_simulacao, mostrar_requisicao, para_local, preparar_pagina, selecionar_sensor, sidebar_base
from theme import pill

preparar_pagina("Histórico", "📈")
cliente = sidebar_base()
sel = selecionar_sensor(cliente)
if not sel:
    st.stop()
sensor, _ = sel

with st.sidebar:
    horas = st.slider("Janela (horas)", 1, 168, 48)
    intervalo = st.selectbox("Intervalo entre pontos", [5, 15, 30, 60], index=2, format_func=lambda m: f"{m} min")
sim = bloco_simulacao("historico")
with st.sidebar:
    st.divider()

st.title(f"📈 Histórico — {sensor['tag']} · {sensor['nome']}")
st.caption(f"{sensor['planta']} · {sensor['linha']}")

r = cliente.historico(sensor["tag"], horas=horas, intervalo_min=intervalo, feature="dashboard-historico", **sim)
mostrar_requisicao(r)
if not r.ok:
    st.error(f"A API respondeu com erro: {r.erro}")
    st.stop()
d = r.data

c1, c2, c3, c4 = st.columns(4)
c1.metric("Pontos retornados", f"{d['pontos_retornados']} / {d['pontos_esperados']}")
c2.metric("Completude", f"{d['completude_pct']:.1f} %")
c3.markdown("**Qualidade do histórico**<br>" + pill(d["completude_status"]), unsafe_allow_html=True)
c4.metric("Lacunas", d["pontos_esperados"] - d["pontos_retornados"])
if d["completude_status"] != "ok":
    st.warning("⚠ Histórico incompleto: há pontos faltando na janela. Os trechos sem dado aparecem como quebras nas linhas.")

if not d["pontos"]:
    st.info("Nenhum ponto retornado para a janela.")
    st.stop()

df = pd.DataFrame(d["pontos"])
df["timestamp"] = para_local(df["timestamp"])
grade = pd.date_range(para_local(pd.Series([d["janela_inicio"]])).iloc[0],
                      para_local(pd.Series([d["janela_fim"]])).iloc[0], freq=f"{d['intervalo_min']}min")
df_grade = df.set_index("timestamp").reindex(grade).rename_axis("timestamp").reset_index()   # NaN onde faltam pontos

aba_g, aba_t, aba_e = st.tabs(["📈 Gráficos", "📋 Tabela", "📊 Estatísticas"])
lim = d["limites"]
with aba_g:
    g1, g2 = st.columns(2)
    g1.plotly_chart(serie_historico(df_grade, "temperatura", f"Temperatura (°C) — últimas {horas}h", "°C", lim["temperatura"]), width="stretch")
    g2.plotly_chart(serie_historico(df_grade, "vibracao", f"Vibração (mm/s) — últimas {horas}h", "mm/s", lim["vibracao"], "#22C55E"), width="stretch")
    st.plotly_chart(serie_historico(df_grade, "corrente", f"Corrente (A) — últimas {horas}h", "A", lim["corrente"], "#A855F7"), width="stretch")
with aba_t:
    tabela = df.rename(columns={"timestamp": "Horário", "temperatura": "Temp. (°C)", "vibracao": "Vib. (mm/s)", "corrente": "Corrente (A)"})
    st.dataframe(tabela.iloc[::-1], hide_index=True, width="stretch", height=380)
    st.download_button("⬇️ Baixar CSV", tabela.to_csv(index=False).encode("utf-8"),
                       file_name=f"historico_{sensor['tag']}.csv", mime="text/csv")
with aba_e:
    est = pd.DataFrame(d["estatisticas"]).T.rename(index={"temperatura": "Temperatura (°C)", "vibracao": "Vibração (mm/s)", "corrente": "Corrente (A)"})
    st.dataframe(est.rename(columns={"min": "Mínimo", "media": "Média", "max": "Máximo"}), width="stretch")
