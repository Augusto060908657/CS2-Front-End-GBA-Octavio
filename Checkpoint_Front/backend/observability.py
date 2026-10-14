"""
backend/observability.py
========================
Registro de observabilidade: toda chamada a /v1/* vira uma linha em SQLite
com os metadados do contrato (quem, de onde, quando, quanto tempo, resultado).

Também calcula os indicadores do Metric Contract a partir dos registros.
"""
from __future__ import annotations

import sqlite3
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import config

COLUNAS = [
    "request_id", "timestamp", "session_id", "feature", "metodo", "endpoint", "caminho", "tag",
    "status_code", "latencia_ms", "contexto_completo", "freshness_s", "completude_pct",
    "severidade", "registros_retornados", "simulacao",
]

_DDL = """
CREATE TABLE IF NOT EXISTS chamadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT, timestamp TEXT NOT NULL, session_id TEXT, feature TEXT,
    metodo TEXT, endpoint TEXT, caminho TEXT, tag TEXT, status_code INTEGER,
    latencia_ms REAL, contexto_completo INTEGER, freshness_s REAL, completude_pct REAL,
    severidade TEXT, registros_retornados INTEGER, simulacao TEXT
);
CREATE INDEX IF NOT EXISTS idx_chamadas_ts ON chamadas(timestamp);
"""


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ObservabilityStore:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_DDL)

    def registrar(self, reg: dict) -> None:
        valores = [reg.get(c) for c in COLUNAS]
        with self._lock:
            self._conn.execute(
                f"INSERT INTO chamadas ({','.join(COLUNAS)}) VALUES ({','.join('?' * len(COLUNAS))})", valores)
            self._conn.commit()

    @staticmethod
    def _where(filtros: dict) -> tuple[str, list]:
        cond, params = [], []
        for campo in ("feature", "session_id", "tag", "status_code", "metodo"):
            if filtros.get(campo) not in (None, ""):
                cond.append(f"{campo} = ?")
                params.append(filtros[campo])
        if filtros.get("endpoint"):
            cond.append("endpoint LIKE ?")
            params.append(f"%{filtros['endpoint']}%")
        if filtros.get("desde"):
            cond.append("timestamp >= ?")
            params.append(filtros["desde"])
        return (" WHERE " + " AND ".join(cond)) if cond else "", params

    def listar(self, filtros: dict, limite: int = 200, offset: int = 0) -> tuple[int, list[dict]]:
        where, params = self._where(filtros)
        with self._lock:
            total = self._conn.execute(f"SELECT COUNT(*) FROM chamadas{where}", params).fetchone()[0]
            linhas = self._conn.execute(
                f"SELECT id, {','.join(COLUNAS)} FROM chamadas{where} ORDER BY id DESC LIMIT ? OFFSET ?",
                [*params, limite, offset]).fetchall()
        regs = [dict(l) for l in linhas]
        for r in regs:
            r["contexto_completo"] = bool(r["contexto_completo"])
        return total, regs


# ─────────────────────────────────────────────
# Indicadores do Metric Contract
# ─────────────────────────────────────────────
def _pct(valores: list[float], q: float) -> float | None:
    return round(float(np.percentile(valores, q)), 2) if valores else None


def _avaliar(valor: float | None, c: dict) -> str:
    if valor is None:
        return "sem_dados"
    if c["direcao"] == "max":
        return "crit" if valor > c["critico"] else "warn" if valor > c["atencao"] else "ok"
    return "crit" if valor < c["critico"] else "warn" if valor < c["atencao"] else "ok"


def calcular_indicadores(store: ObservabilityStore, janela_min: int, bucket_s: int,
                         excluir_simulacoes: bool = False) -> dict:
    agora = datetime.now(timezone.utc)
    desde = (agora - timedelta(minutes=janela_min)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    _, regs = store.listar({"desde": desde}, limite=100000)
    dados = [r for r in regs if (r["endpoint"] or "").startswith(config.PREFIXO_DADOS)
             and not (excluir_simulacoes and r["simulacao"])]
    leituras = [r for r in dados if r["endpoint"] == config.ENDPOINT_LEITURA and r["freshness_s"] is not None]
    historicos = [r for r in dados if r["endpoint"] == config.ENDPOINT_HISTORICO and r["completude_pct"] is not None]

    n = len(dados)
    lat = [r["latencia_ms"] for r in dados]
    fresh = [r["freshness_s"] for r in leituras]
    valores = {
        "freshness_p95_s": _pct(fresh, 95),
        "taxa_freshness_ok": round(100 * sum(f <= config.FRESHNESS_ATENCAO_S for f in fresh) / len(fresh), 2) if fresh else None,
        "completude_historico": round(float(np.mean([r["completude_pct"] for r in historicos])), 2) if historicos else None,
        "latencia_p95_ms": _pct(lat, 95),
        "taxa_erro_5xx": round(100 * sum(r["status_code"] >= 500 for r in dados) / n, 2) if n else None,
        "conformidade_headers": round(100 * sum(r["contexto_completo"] for r in dados) / n, 2) if n else None,
    }
    amostras = {"freshness_p95_s": len(fresh), "taxa_freshness_ok": len(fresh), "completude_historico": len(historicos),
                "latencia_p95_ms": n, "taxa_erro_5xx": n, "conformidade_headers": n}

    indicadores = []
    for c in config.METRIC_CONTRACT:
        v = valores[c["id"]]
        status = _avaliar(v, c)
        acao = c["acao_critico"] if status == "crit" else c["acao_atencao"] if status == "warn" else "Nenhuma ação necessária."
        indicadores.append({**c, "valor": v, "status": status, "amostra": amostras[c["id"]], "acao_recomendada": acao})

    # séries temporais por bucket
    grupos: dict[int, list[dict]] = defaultdict(list)
    for r in dados:
        t = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).timestamp()
        grupos[int(t // bucket_s) * bucket_s].append(r)
    series = []
    for b in sorted(grupos):
        g = grupos[b]
        fr = [r["freshness_s"] for r in g if r["freshness_s"] is not None]
        cp = [r["completude_pct"] for r in g if r["completude_pct"] is not None]
        series.append({
            "bucket": datetime.fromtimestamp(b, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "chamadas": len(g),
            "latencia_media_ms": round(float(np.mean([r["latencia_ms"] for r in g])), 2),
            "latencia_p95_ms": _pct([r["latencia_ms"] for r in g], 95),
            "status_2xx": sum(200 <= r["status_code"] < 300 for r in g),
            "status_4xx": sum(400 <= r["status_code"] < 500 for r in g),
            "status_5xx": sum(r["status_code"] >= 500 for r in g),
            "freshness_p95_s": _pct(fr, 95),
            "freshness_ok_pct": round(100 * sum(f <= config.FRESHNESS_ATENCAO_S for f in fr) / len(fr), 2) if fr else None,
            "completude_media_pct": round(float(np.mean(cp)), 2) if cp else None,
        })

    resumo = {
        "sucesso_pct": round(100 * sum(200 <= r["status_code"] < 300 for r in dados) / n, 2) if n else None,
        "latencia_ms": {"p50": _pct(lat, 50), "p95": _pct(lat, 95), "p99": _pct(lat, 99),
                        "media": round(float(np.mean(lat)), 2) if lat else None, "max": round(max(lat), 2) if lat else None},
        "por_feature": dict(Counter(r["feature"] or "(sem header)" for r in dados)),
        "por_endpoint": dict(Counter(r["endpoint"] for r in dados)),
        "por_status": dict(Counter(str(r["status_code"]) for r in dados)),
        "sessoes_distintas": len({r["session_id"] for r in dados if r["session_id"]}),
    }
    return {"gerado_em": agora_iso(), "janela_min": janela_min, "bucket_s": bucket_s,
            "total_chamadas": n, "indicadores": indicadores, "resumo": resumo, "series": series}


def exportar_csv(registros: list[dict]) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", *COLUNAS], extrasaction="ignore")
    w.writeheader()
    w.writerows(registros)
    return buf.getvalue()
