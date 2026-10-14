"""
backend/main.py
===============
Forzy · Digital Twin — Sensor Monitoring API (FastAPI)

Endpoints:
    GET /v1/sensores                              catálogo (Planta -> Linha -> TAG)
    GET /v1/sensores/{tag}/leitura-atual          leitura atual + severidade + freshness
    GET /v1/sensores/{tag}/historico              série histórica + completude
    GET /v1/observabilidade                       registros de chamadas (para a Governança)
    GET /v1/observabilidade/indicadores           indicadores do Metric Contract + séries
    GET /v1/observabilidade/export                registros em CSV

Um middleware registra, em CADA chamada a /v1/*, os headers de contexto
(X-Session-Id, X-Feature), timestamp (UTC) e latência — ver observability.py.

Rodar:  uvicorn backend.main:app --reload --port 8000   (a partir da raiz do projeto)
"""
from __future__ import annotations

import logging
import random
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from . import config, provider
from .observability import ObservabilityStore, agora_iso, calcular_indicadores, exportar_csv
from .registry import buscar_sensor, listar_catalogo

log = logging.getLogger("sensor-api")

app = FastAPI(
    title="Forzy · Digital Twin — Sensor Monitoring API",
    version="1.0.0",
    description=(
        "API do provider de Sensores com observabilidade embutida. Envie os headers "
        "`X-Session-Id` e `X-Feature` em cada chamada; todas as chamadas a `/v1/*` "
        "são registradas e expostas em `/v1/observabilidade`."
    ),
)
store = ObservabilityStore(config.DB_PATH)


# ─────────────────────────────────────────────
# Middleware de observabilidade
# ─────────────────────────────────────────────
def _limpar(valor: str | None, tamanho: int = 64) -> str | None:
    valor = (valor or "").strip()
    return valor[:tamanho] if valor else None


@app.middleware("http")
async def observabilidade(request: Request, call_next):
    if not request.url.path.startswith("/v1/"):
        return await call_next(request)

    inicio = time.perf_counter()
    request_id = uuid4().hex[:12]
    request.state.obs = {}
    try:
        response = await call_next(request)
    except Exception:  # erro não tratado -> 500 registrado
        log.exception("Erro não tratado em %s", request.url.path)
        response = JSONResponse({"detail": "Erro interno do servidor"}, status_code=500)
    latencia_ms = round((time.perf_counter() - inicio) * 1000, 2)

    session_id = _limpar(request.headers.get(config.HEADER_SESSION))
    feature = _limpar(request.headers.get(config.HEADER_FEATURE))
    rota = request.scope.get("route")
    registro = {
        "request_id": request_id, "timestamp": agora_iso(),
        "session_id": session_id, "feature": feature,
        "metodo": request.method, "endpoint": getattr(rota, "path", request.url.path),
        "caminho": request.url.path, "tag": _limpar(request.path_params.get("tag"), 32),
        "status_code": response.status_code, "latencia_ms": latencia_ms,
        "contexto_completo": int(bool(session_id and feature)),
        **request.state.obs,
    }
    try:
        await run_in_threadpool(store.registrar, registro)
    except Exception:  # observabilidade nunca derruba a requisição
        log.exception("Falha ao registrar observabilidade")

    response.headers["X-Request-Id"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{latencia_ms:.2f}"
    return response


# ─────────────────────────────────────────────
# Injeção de falhas (SOMENTE demonstração/validação dos limiares)
# ─────────────────────────────────────────────
def simulacao(
    simular_atraso_s: int = Query(0, ge=0, le=3600, description="[demo] soma segundos ao atraso do sensor (freshness)"),
    simular_falhas: float = Query(0.0, ge=0, le=1, description="[demo] fração extra de pontos perdidos no histórico"),
    simular_latencia_ms: int = Query(0, ge=0, le=5000, description="[demo] latência artificial adicional"),
    simular_erro: bool = Query(False, description="[demo] força HTTP 500"),
) -> dict:
    return {"atraso_s": simular_atraso_s, "falhas": simular_falhas, "latencia_ms": simular_latencia_ms, "erro": simular_erro}


def _aplicar(request: Request, sim: dict, usados: tuple[str, ...]) -> dict:
    """Aplica latência/erro simulados e anota o que foi injetado no registro."""
    ativos = [f"{k}={sim[k]}" for k in usados if sim[k]]
    request.state.obs["simulacao"] = ",".join(ativos) or None
    # latência "natural" da fonte de dados + latência injetada
    time.sleep(random.uniform(0.015, 0.09) + sim["latencia_ms"] / 1000)
    if sim["erro"]:
        raise HTTPException(500, "Falha simulada (injeção de falhas de demonstração)")
    return sim


def _sensor_ou_404(tag: str) -> dict:
    sensor = buscar_sensor(tag)
    if not sensor:
        raise HTTPException(404, f"Sensor '{tag}' não encontrado")
    return sensor


# ─────────────────────────────────────────────
# Provider de Sensores
# ─────────────────────────────────────────────
@app.get("/health", tags=["infra"], summary="Healthcheck (não é registrado)")
def health():
    return {"status": "ok", "hora_utc": agora_iso()}


@app.get("/v1/sensores", tags=["sensores"], summary="Catálogo de sensores")
def catalogo(request: Request):
    itens = listar_catalogo()
    request.state.obs["registros_retornados"] = len(itens)
    return {"total": len(itens), "sensores": itens}


@app.get("/v1/sensores/{tag}/leitura-atual", tags=["sensores"], summary="Leitura atual do sensor")
def leitura_atual(tag: str, request: Request, sim: dict = Depends(simulacao)):
    sensor = _sensor_ou_404(tag)
    _aplicar(request, sim, ("atraso_s", "latencia_ms", "erro"))
    dado = provider.leitura_atual(sensor, atraso_extra_s=sim["atraso_s"])
    request.state.obs.update(freshness_s=dado["freshness_s"], severidade=dado["severidade"], registros_retornados=1)
    return dado


@app.get("/v1/sensores/{tag}/historico", tags=["sensores"], summary="Histórico do sensor")
def historico(
    tag: str, request: Request,
    horas: int = Query(48, ge=1, le=168, description="janela em horas"),
    intervalo_min: int = Query(config.HISTORICO_INTERVALO_PADRAO_MIN, ge=5, le=120, description="intervalo entre pontos (min)"),
    sim: dict = Depends(simulacao),
):
    sensor = _sensor_ou_404(tag)
    _aplicar(request, sim, ("falhas", "latencia_ms", "erro"))
    dado = provider.historico(sensor, horas, intervalo_min, falhas_extra=sim["falhas"])
    request.state.obs.update(completude_pct=dado["completude_pct"], registros_retornados=dado["pontos_retornados"])
    return dado


# ─────────────────────────────────────────────
# Observabilidade (consumida pela Governança em IA)
# ─────────────────────────────────────────────
@app.get("/v1/observabilidade", tags=["observabilidade"], summary="Registros de chamadas coletados")
def observabilidade_registros(
    limite: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0),
    endpoint: str | None = None, feature: str | None = None, session_id: str | None = None,
    tag: str | None = None, status_code: int | None = None, metodo: str | None = None,
):
    filtros = dict(endpoint=endpoint, feature=feature, session_id=session_id, tag=tag,
                   status_code=status_code, metodo=metodo)
    total, regs = store.listar(filtros, limite, offset)
    return {"total": total, "limite": limite, "offset": offset, "registros": regs}


@app.get("/v1/observabilidade/indicadores", tags=["observabilidade"], summary="Indicadores do Metric Contract")
def observabilidade_indicadores(
    janela_min: int = Query(60, ge=1, le=10080, description="janela de análise em minutos"),
    bucket_s: int = Query(60, ge=10, le=3600, description="tamanho do bucket das séries (s)"),
    excluir_simulacoes: bool = Query(False, description="ignora chamadas com falha injetada"),
):
    return calcular_indicadores(store, janela_min, bucket_s, excluir_simulacoes)


@app.get("/v1/observabilidade/export", tags=["observabilidade"], summary="Exporta os registros em CSV")
def observabilidade_export(limite: int = Query(5000, ge=1, le=100000)):
    _, regs = store.listar({}, limite)
    return Response(exportar_csv(regs), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=observabilidade.csv"})
