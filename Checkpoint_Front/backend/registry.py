"""
backend/registry.py
===================
Cadastro de ativos (Planta -> Linha/Área -> Equipamento) herdado da Sprint 3.
No provider de Sensores, cada equipamento (TAG) é a "fonte" das leituras.

Para usar dados reais, troque SENSORES_DB por leitura de banco/API mantendo o
mesmo formato; o restante do back-end não precisa mudar.
"""
from __future__ import annotations

SENSORES_DB: list[dict] = [
    {"planta": "Planta A", "linhas": [
        {"linha_nome": "Linha 1 — Produção", "equipamentos": [
            {"tag": "MT-001", "nome": "Motor Ventilação Principal", "modelo": "WEG W22 90L", "potencia": "7,5 kW",
             "base": {"temp_celsius": 48.0, "vib_mm_s": 1.8, "corrente_ampere": 32.1, "rpm": 1450}},
            {"tag": "MT-002", "nome": "Motor Bomba Hidráulica", "modelo": "WEG W22 100L", "potencia": "11 kW",
             "base": {"temp_celsius": 58.0, "vib_mm_s": 3.9, "corrente_ampere": 38.4, "rpm": 1430}},
        ]},
        {"linha_nome": "Linha 2 — Empacotamento", "equipamentos": [
            {"tag": "MT-003", "nome": "Motor Esteira de Carga", "modelo": "WEG W22 80L", "potencia": "5,5 kW",
             "base": {"temp_celsius": 44.0, "vib_mm_s": 1.2, "corrente_ampere": 28.7, "rpm": 1455}},
        ]},
    ]},
    {"planta": "Planta B", "linhas": [
        {"linha_nome": "Linha 1 — Compressão", "equipamentos": [
            {"tag": "MT-004", "nome": "Motor Compressor #1", "modelo": "Siemens 1LE1", "potencia": "15 kW",
             "base": {"temp_celsius": 71.0, "vib_mm_s": 5.8, "corrente_ampere": 52.0, "rpm": 1390}},
        ]},
        {"linha_nome": "Linha 2 — Utilidades", "equipamentos": [
            {"tag": "MT-005", "nome": "Motor Bomba de Retorno", "modelo": "WEG W22 90L", "potencia": "7,5 kW",
             "base": {"temp_celsius": 46.0, "vib_mm_s": 2.1, "corrente_ampere": 29.5, "rpm": 1448}},
        ]},
    ]},
]

# Comportamento de coleta simulado por TAG (para os indicadores terem variação realista):
#   p_atraso  -> chance de a leitura chegar atrasada (freshness alto)
#   p_lacuna  -> fração de pontos faltando no histórico (completude baixa)
PERFIL_COLETA: dict[str, dict] = {
    "MT-001": {"p_atraso": 0.00, "p_lacuna": 0.005},
    "MT-002": {"p_atraso": 0.02, "p_lacuna": 0.02},
    "MT-003": {"p_atraso": 0.00, "p_lacuna": 0.005},
    "MT-004": {"p_atraso": 0.25, "p_lacuna": 0.08},   # sensor instável
    "MT-005": {"p_atraso": 0.00, "p_lacuna": 0.005},
}
PERFIL_PADRAO = {"p_atraso": 0.0, "p_lacuna": 0.005}


def listar_catalogo() -> list[dict]:
    """Lista achatada: cada item traz planta e linha de origem."""
    itens = []
    for p in SENSORES_DB:
        for l in p["linhas"]:
            for eq in l["equipamentos"]:
                itens.append({
                    "tag": eq["tag"], "nome": eq["nome"], "planta": p["planta"],
                    "linha": l["linha_nome"], "modelo": eq["modelo"], "potencia": eq["potencia"],
                })
    return itens


def buscar_sensor(tag: str) -> dict | None:
    for p in SENSORES_DB:
        for l in p["linhas"]:
            for eq in l["equipamentos"]:
                if eq["tag"] == tag:
                    return {**eq, "planta": p["planta"], "linha": l["linha_nome"]}
    return None
