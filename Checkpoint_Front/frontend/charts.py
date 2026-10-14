"""frontend/charts.py — gráficos Plotly (uma camada gráfica por indicador do contrato)."""
import plotly.graph_objects as go

BG, GRID, TXT = "#1E2233", "#252A3D", "#8B9AC0"
AZUL, VERDE, AMBAR, VERMELHO = "#3B82F6", "#22C55E", "#F59E0B", "#EF4444"


def _base(fig, titulo, altura=300, legenda=False):
    fig.update_layout(title=titulo, paper_bgcolor=BG, plot_bgcolor=BG, font=dict(color=TXT, size=12),
                      xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID), showlegend=legenda,
                      height=altura, margin=dict(l=0, r=0, t=40, b=0), hovermode="x unified")
    return fig


def _limiares(fig, atencao, critico):
    if atencao is not None:
        fig.add_hline(y=atencao, line_dash="dash", line_color=AMBAR, line_width=1.3,
                      annotation_text=f"Atenção ({atencao:g})", annotation_font_color=AMBAR)
    if critico is not None:
        fig.add_hline(y=critico, line_dash="dash", line_color=VERMELHO, line_width=1.3,
                      annotation_text=f"Crítico ({critico:g})", annotation_font_color=VERMELHO)


def serie_historico(df, coluna, titulo, unidade, limite, cor=AZUL):
    """Linha do histórico com quebras onde faltam pontos (lacunas) e o limite operacional."""
    fig = go.Figure(go.Scatter(x=df["timestamp"], y=df[coluna], mode="lines", connectgaps=False,
                               line=dict(color=cor, width=2),
                               hovertemplate="%{x|%d/%m %H:%M}<br><b>%{y:.2f} " + unidade + "</b><extra></extra>"))
    if limite:
        fig.add_hline(y=limite, line_dash="dash", line_color=AMBAR, annotation_text=f"Limite: {limite:g} {unidade}",
                      annotation_font_color=AMBAR)
    return _base(fig, titulo)


def linha_limiar(df, x, y, titulo, ind, nome_y, markers=False):
    """Série temporal + linhas de limiar vindas do contrato (indicador `ind`)."""
    fig = go.Figure(go.Scatter(x=df[x], y=df[y], mode="lines+markers" if markers else "lines", name=nome_y,
                               line=dict(color=AZUL, width=2), connectgaps=True,
                               hovertemplate="%{x|%H:%M:%S}<br><b>%{y:.1f} " + ind["unidade"] + "</b><extra></extra>"))
    _limiares(fig, ind["atencao"], ind["critico"])
    fig.update_yaxes(title=ind["unidade"])
    return _base(fig, titulo)


def barras_status(series_df):
    fig = go.Figure()
    for col, nome, cor in (("status_2xx", "2xx", VERDE), ("status_4xx", "4xx", AMBAR), ("status_5xx", "5xx", VERMELHO)):
        fig.add_trace(go.Bar(x=series_df["bucket"], y=series_df[col], name=nome, marker_color=cor))
    fig.update_layout(barmode="stack")
    return _base(fig, "Chamadas por classe de status", legenda=True)


def gauge(valor, ind, titulo):
    """Gauge para indicadores de tipo 'quanto maior melhor' (direcao == min)."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=valor if valor is not None else 0, number=dict(suffix="%", font=dict(color="#F0F4FF")),
        title=dict(text=titulo, font=dict(size=14, color=TXT)),
        gauge=dict(axis=dict(range=[80, 100], tickcolor=TXT), bar=dict(color=AZUL), bgcolor=BG,
                   steps=[dict(range=[80, ind["critico"]], color="rgba(239,68,68,.35)"),
                          dict(range=[ind["critico"], ind["atencao"]], color="rgba(245,158,11,.35)"),
                          dict(range=[ind["atencao"], 100], color="rgba(34,197,94,.30)")])))
    fig.update_layout(paper_bgcolor=BG, height=260, margin=dict(l=20, r=20, t=60, b=10), font=dict(color=TXT))
    return fig


def barras_categoria(dic, titulo):
    fig = go.Figure(go.Bar(x=list(dic.values()), y=list(dic.keys()), orientation="h", marker_color=AZUL))
    fig.update_yaxes(autorange="reversed")
    return _base(fig, titulo, altura=260)
