"""
backend/provider.py
===================
Provider de Sensores: produz a leitura atual e o histórico de cada TAG.

Os dados são SIMULADOS, porém DETERMINÍSTICOS: para a mesma TAG e o mesmo
instante o valor é sempre o mesmo (gerador semeado por TAG + janela de tempo).
Isso evita gráficos "pulando" a cada chamada e torna os testes reprodutíveis.

Para integrar uma fonte real (banco/IoT), substitua apenas `leitura_atual()` e
`historico()` mantendo o formato dos dicionários retornados.
"""
from __future__ import annotations

import math
import zlib
from datetime import datetime, timedelta, timezone

import numpy as np

from . import config
from .registry import PERFIL_COLETA, PERFIL_PADRAO


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rng(tag: str, *chaves: int) -> np.random.Generator:
    return np.random.default_rng([zlib.crc32(tag.encode()), *[int(c) for c in chaves]])


# ─────────────────────────────────────────────
# Classificação de severidade (regra da Sprint 3)
# ─────────────────────────────────────────────
def calcular_severidade(temp: float, vib: float, corrente: float) -> str:
    L, f = config.LIMITES, config.FATOR_ATENCAO
    if temp > L["temp_celsius"] or vib > L["vib_mm_s"] or corrente > L["corrente_ampere"]:
        return "crit"
    if temp > L["temp_celsius"] * f or vib > L["vib_mm_s"] * f or corrente > L["corrente_ampere"] * f:
        return "warn"
    return "ok"


def metrica_mais_critica(temp: float, vib: float, corrente: float) -> str:
    cand = [("Temperatura", temp / config.LIMITES["temp_celsius"]),
            ("Vibração", vib / config.LIMITES["vib_mm_s"]),
            ("Corrente", corrente / config.LIMITES["corrente_ampere"])]
    return max(cand, key=lambda c: c[1])[0]


def status_freshness(freshness_s: float) -> str:
    if freshness_s > config.FRESHNESS_CRITICO_S:
        return "crit"
    if freshness_s > config.FRESHNESS_ATENCAO_S:
        return "warn"
    return "ok"


def status_completude(completude_pct: float) -> str:
    if completude_pct < config.COMPLETUDE_CRITICO_PCT:
        return "crit"
    if completude_pct < config.COMPLETUDE_ATENCAO_PCT:
        return "warn"
    return "ok"


# ─────────────────────────────────────────────
# Leitura atual
# ─────────────────────────────────────────────
def leitura_atual(sensor: dict, agora: datetime | None = None, atraso_extra_s: int = 0) -> dict:
    agora = agora or datetime.now(timezone.utc)
    tag, base = sensor["tag"], sensor["base"]
    slot = int(agora.timestamp() // config.INTERVALO_AMOSTRAGEM_S)

    r = _rng(tag, slot)
    temp = round(base["temp_celsius"] + r.normal(0, 0.8), 1)
    vib = round(max(base["vib_mm_s"] + r.normal(0, 0.12), 0.1), 2)
    corrente = round(base["corrente_ampere"] + r.normal(0, 0.8), 1)
    rpm = int(base["rpm"] + r.normal(0, 4))

    # Atraso de publicação do sensor (freshness): normal 5–40 s; sensores
    # instáveis têm picos de 150–420 s; `atraso_extra_s` é a injeção de falha.
    perfil = PERFIL_COLETA.get(tag, PERFIL_PADRAO)
    r2 = _rng(tag + ":lag", slot)
    atraso = 5 + r2.uniform(0, 35)
    if r2.random() < perfil["p_atraso"]:
        atraso = r2.uniform(150, 420)
    atraso += atraso_extra_s
    ts_medicao = agora - timedelta(seconds=atraso)
    freshness = round((agora - ts_medicao).total_seconds(), 1)

    return {
        "tag": tag, "nome": sensor["nome"], "planta": sensor["planta"], "linha": sensor["linha"],
        "modelo": sensor["modelo"], "potencia": sensor["potencia"],
        "timestamp_medicao": _iso(ts_medicao),
        "timestamp_consulta": _iso(agora),
        "leituras": {"temperatura_c": temp, "vibracao_mm_s": vib, "corrente_a": corrente, "rpm": rpm},
        "limites": {"temperatura_c": config.LIMITES["temp_celsius"],
                    "vibracao_mm_s": config.LIMITES["vib_mm_s"],
                    "corrente_a": config.LIMITES["corrente_ampere"]},
        "severidade": calcular_severidade(temp, vib, corrente),
        "metrica_critica": metrica_mais_critica(temp, vib, corrente),
        "freshness_s": freshness,
        "freshness_status": status_freshness(freshness),
    }


# ─────────────────────────────────────────────
# Histórico
# ─────────────────────────────────────────────
def historico(sensor: dict, horas: int, intervalo_min: int, agora: datetime | None = None,
              falhas_extra: float = 0.0) -> dict:
    agora = agora or datetime.now(timezone.utc)
    tag, base = sensor["tag"], sensor["base"]
    passo = intervalo_min * 60
    esperados = max(horas * 60 // intervalo_min, 1)
    ultimo_slot = int(agora.timestamp() // passo)
    p_lacuna = min(PERFIL_COLETA.get(tag, PERFIL_PADRAO)["p_lacuna"] + falhas_extra, 1.0)

    pontos = []
    for slot in range(ultimo_slot - esperados + 1, ultimo_slot + 1):
        t = slot * passo
        r = _rng(tag, t)
        if r.random() < p_lacuna:      # ponto perdido na coleta
            continue
        ciclo = math.sin(2 * math.pi * t / 86400)
        pontos.append({
            "timestamp": _iso(datetime.fromtimestamp(t, tz=timezone.utc)),
            "temperatura": round(base["temp_celsius"] + 2.5 * ciclo + r.normal(0, 0.8), 2),
            "vibracao": round(max(base["vib_mm_s"] + 0.25 * math.sin(4 * math.pi * t / 86400) + r.normal(0, 0.12), 0.1), 2),
            "corrente": round(base["corrente_ampere"] + 1.5 * ciclo + r.normal(0, 0.6), 2),
        })

    completude = round(len(pontos) / esperados * 100, 2)
    stats = {}
    if pontos:
        for campo in ("temperatura", "vibracao", "corrente"):
            vals = [p[campo] for p in pontos]
            stats[campo] = {"min": round(min(vals), 2), "media": round(sum(vals) / len(vals), 2), "max": round(max(vals), 2)}

    return {
        "tag": tag, "nome": sensor["nome"], "planta": sensor["planta"], "linha": sensor["linha"],
        "janela_horas": horas, "intervalo_min": intervalo_min,
        "janela_inicio": _iso(datetime.fromtimestamp((ultimo_slot - esperados + 1) * passo, tz=timezone.utc)),
        "janela_fim": _iso(datetime.fromtimestamp(ultimo_slot * passo, tz=timezone.utc)),
        "pontos_esperados": esperados, "pontos_retornados": len(pontos),
        "completude_pct": completude, "completude_status": status_completude(completude),
        "limites": {"temperatura": config.LIMITES["temp_celsius"], "vibracao": config.LIMITES["vib_mm_s"],
                    "corrente": config.LIMITES["corrente_ampere"]},
        "estatisticas": stats, "pontos": pontos,
    }
