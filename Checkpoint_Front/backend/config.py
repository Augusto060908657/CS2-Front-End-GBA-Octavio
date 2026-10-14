"""
backend/config.py
=================
Configurações centrais do Sensor Monitoring API.

É AQUI que ficam o "Metric Contract" (contrato de observabilidade) e os
limiares de cada indicador. Os valores abaixo são a proposta inicial do grupo:
ajuste-os para que fiquem IGUAIS aos definidos no relatório de Governança em IA.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("OBS_DB_PATH", BASE_DIR / "data" / "observabilidade.db"))

# ─────────────────────────────────────────────
# Headers de contexto enviados pelo front em TODA chamada
# ─────────────────────────────────────────────
HEADER_SESSION = "X-Session-Id"   # quem chamou (sessão do usuário no front)
HEADER_FEATURE = "X-Feature"      # de qual funcionalidade partiu a chamada

# ─────────────────────────────────────────────
# Limites operacionais dos motores (herdados da Sprint 3)
# ─────────────────────────────────────────────
LIMITES = {"temp_celsius": 60.0, "vib_mm_s": 4.5, "corrente_ampere": 50.0}
FATOR_ATENCAO = 0.90  # a partir de 90% do limite o sensor entra em "Atenção"

# ─────────────────────────────────────────────
# Parâmetros da fonte de dados dos sensores
# ─────────────────────────────────────────────
INTERVALO_AMOSTRAGEM_S = 60        # cada sensor publica 1 leitura por minuto
HISTORICO_INTERVALO_PADRAO_MIN = 30

# Limiares usados para classificar CADA chamada (mesmos do contrato abaixo)
FRESHNESS_ATENCAO_S = 120          # 2 amostragens perdidas
FRESHNESS_CRITICO_S = 300          # 5 amostragens perdidas
COMPLETUDE_ATENCAO_PCT = 95.0
COMPLETUDE_CRITICO_PCT = 90.0

# Endpoints de dados do provider de Sensores (entram nos indicadores).
# As chamadas a /v1/observabilidade* também são registradas (auditoria da
# auditoria), mas NÃO entram no cálculo dos indicadores.
PREFIXO_DADOS = "/v1/sensores"
ENDPOINT_LEITURA = "/v1/sensores/{tag}/leitura-atual"
ENDPOINT_HISTORICO = "/v1/sensores/{tag}/historico"

# ─────────────────────────────────────────────
# METRIC CONTRACT — um item por indicador
#   direcao "max": quanto MENOR melhor (estoura quando valor > limiar)
#   direcao "min": quanto MAIOR melhor (estoura quando valor < limiar)
# ─────────────────────────────────────────────
METRIC_CONTRACT: list[dict] = [
    {
        "id": "freshness_p95_s",
        "nome": "Freshness (idade do dado) — p95",
        "descricao": "Idade da leitura devolvida: segundos entre o timestamp da medição do sensor e o instante da chamada.",
        "formula": "p95( timestamp_da_chamada − timestamp_da_medição ) nas chamadas de leitura-atual",
        "unidade": "s", "direcao": "max",
        "baseline": 60.0, "atencao": FRESHNESS_ATENCAO_S, "critico": FRESHNESS_CRITICO_S,
        "grafico": "Gráfico de linha (série temporal por chamada) com linhas de limiar",
        "acao_atencao": "Verificar conectividade do gateway/broker do sensor e abrir ticket para a equipe de dados.",
        "acao_critico": "Marcar a leitura como obsoleta no front, notificar o responsável pelo ativo e acionar contingência de coleta manual.",
    },
    {
        "id": "taxa_freshness_ok",
        "nome": "Taxa de completude de Freshness",
        "descricao": "Proporção de leituras entregues dentro do SLA de atualização.",
        "formula": f"leituras com freshness ≤ {FRESHNESS_ATENCAO_S}s ÷ total de leituras × 100",
        "unidade": "%", "direcao": "min",
        "baseline": 98.0, "atencao": 95.0, "critico": 90.0,
        "grafico": "Gráfico de linha da taxa por janela de tempo",
        "acao_atencao": "Investigar quais TAGs concentram atrasos e revisar a frequência de coleta.",
        "acao_critico": "Escalar ao time de plataforma, congelar decisões automáticas que dependam do dado e reportar à Governança.",
    },
    {
        "id": "completude_historico",
        "nome": "Completude do histórico",
        "descricao": "Pontos efetivamente retornados versus pontos esperados na janela consultada.",
        "formula": "pontos_retornados ÷ pontos_esperados × 100 (média nas chamadas de historico)",
        "unidade": "%", "direcao": "min",
        "baseline": 98.0, "atencao": COMPLETUDE_ATENCAO_PCT, "critico": COMPLETUDE_CRITICO_PCT,
        "grafico": "Gráfico de linha com marcadores; lacunas visíveis nas séries do histórico",
        "acao_atencao": "Listar as lacunas por TAG e verificar falhas intermitentes de coleta.",
        "acao_critico": "Sinalizar o histórico como incompleto em relatórios/modelos e abrir incidente de qualidade de dados.",
    },
    {
        "id": "latencia_p95_ms",
        "nome": "Latência da API — p95",
        "descricao": "Tempo total que a API levou para processar a chamada (medido no servidor).",
        "formula": "p95( latencia_ms ) nas chamadas aos endpoints de sensores",
        "unidade": "ms", "direcao": "max",
        "baseline": 120.0, "atencao": 300.0, "critico": 800.0,
        "grafico": "Gráfico de linha (latência por chamada) com linhas de limiar",
        "acao_atencao": "Analisar as chamadas mais lentas por endpoint/funcionalidade e revisar consultas e carga.",
        "acao_critico": "Escalar para o time de back-end, ativar cache/limite de janela do histórico e avaliar escalar o serviço.",
    },
    {
        "id": "taxa_erro_5xx",
        "nome": "Taxa de erro do servidor (5xx)",
        "descricao": "Proporção de chamadas que terminaram em erro interno da API.",
        "formula": "chamadas com status ≥ 500 ÷ total de chamadas × 100",
        "unidade": "%", "direcao": "max",
        "baseline": 0.0, "atencao": 1.0, "critico": 5.0,
        "grafico": "Barras empilhadas por classe de status (2xx/4xx/5xx) ao longo do tempo",
        "acao_atencao": "Inspecionar os registros com erro (endpoint, TAG, funcionalidade) e corrigir a causa-raiz.",
        "acao_critico": "Abrir incidente, considerar rollback da última versão e comunicar os consumidores do endpoint.",
    },
    {
        "id": "conformidade_headers",
        "nome": "Conformidade dos headers de contexto",
        "descricao": "Proporção de chamadas que trouxeram X-Session-Id e X-Feature (rastreabilidade: quem e de onde).",
        "formula": "chamadas com ambos os headers ÷ total de chamadas × 100",
        "unidade": "%", "direcao": "min",
        "baseline": 100.0, "atencao": 99.0, "critico": 95.0,
        "grafico": "Gauge (indicador de ponteiro) com faixas de limiar",
        "acao_atencao": "Identificar o cliente que não envia os headers e orientar a correção.",
        "acao_critico": "Passar a rejeitar (HTTP 400) chamadas sem contexto e tratar a lacuna como falha de auditabilidade.",
    },
]
