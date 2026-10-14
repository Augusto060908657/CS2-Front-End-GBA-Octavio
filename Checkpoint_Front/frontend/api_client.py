"""
frontend/api_client.py
======================
Cliente HTTP da Sensor Monitoring API, feito com `requests`.

Toda chamada envia os headers de contexto exigidos pela Governança:
    X-Session-Id  -> identifica a sessão de quem chamou
    X-Feature     -> identifica a funcionalidade do front que originou a chamada

Este módulo não depende de Streamlit: é reutilizado pelo script
`scripts/consumir_api.py`.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

import requests

TIMEOUT_S = 10


@dataclass
class ApiResult:
    ok: bool
    status: int | None = None
    data: dict | None = None
    erro: str | None = None
    metodo: str = "GET"
    url: str = ""
    latencia_cliente_ms: float = 0.0
    latencia_servidor_ms: float | None = None
    request_id: str | None = None
    extra: dict = field(default_factory=dict)

    def resumo(self) -> str:
        if self.status is None:
            return f"{self.metodo} {self.url} → sem resposta ({self.erro})"
        srv = f"{self.latencia_servidor_ms:.0f} ms" if self.latencia_servidor_ms is not None else "—"
        return (f"{self.metodo} {self.url} → {self.status} · cliente {self.latencia_cliente_ms:.0f} ms · "
                f"servidor {srv} · request-id {self.request_id or '—'}")


class ApiClient:
    def __init__(self, base_url: str, session_id: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id or f"cli-{uuid.uuid4().hex[:10]}"

    # ── núcleo ───────────────────────────────────────────
    def _get(self, path: str, feature: str | None, params: dict | None = None,
             enviar_headers: bool = True) -> ApiResult:
        headers = {}
        if enviar_headers:
            headers = {"X-Session-Id": self.session_id, "X-Feature": feature or "nao-informada"}
        params = {k: v for k, v in (params or {}).items() if v not in (None, "", False, 0, 0.0)}
        url = f"{self.base_url}{path}"
        t0 = time.perf_counter()
        try:
            r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT_S)
        except requests.RequestException as e:
            return ApiResult(False, erro=type(e).__name__, url=path,
                             latencia_cliente_ms=(time.perf_counter() - t0) * 1000)
        ms = (time.perf_counter() - t0) * 1000
        try:
            corpo = r.json()
        except ValueError:
            corpo = None
        srv = r.headers.get("X-Process-Time-Ms")
        return ApiResult(
            ok=r.ok, status=r.status_code, data=corpo, url=path, latencia_cliente_ms=ms,
            latencia_servidor_ms=float(srv) if srv else None, request_id=r.headers.get("X-Request-Id"),
            erro=None if r.ok else (corpo or {}).get("detail", r.reason) if isinstance(corpo, dict) else r.reason,
            extra={"texto": r.text if corpo is None else None},
        )

    # ── endpoints ────────────────────────────────────────
    def health(self) -> ApiResult:
        return self._get("/health", None, enviar_headers=False)

    def sensores(self, feature="catalogo-sensores") -> ApiResult:
        return self._get("/v1/sensores", feature)

    def leitura_atual(self, tag: str, feature="dashboard-leitura-atual", **sim) -> ApiResult:
        return self._get(f"/v1/sensores/{tag}/leitura-atual", feature, sim)

    def historico(self, tag: str, horas=48, intervalo_min=30, feature="dashboard-historico", **sim) -> ApiResult:
        return self._get(f"/v1/sensores/{tag}/historico", feature,
                         {"horas": horas, "intervalo_min": intervalo_min, **sim})

    def observabilidade(self, feature="dashboard-observabilidade", **filtros) -> ApiResult:
        return self._get("/v1/observabilidade", feature, filtros)

    def indicadores(self, janela_min=60, bucket_s=60, excluir_simulacoes=False,
                    feature="dashboard-observabilidade") -> ApiResult:
        return self._get("/v1/observabilidade/indicadores", feature,
                         {"janela_min": janela_min, "bucket_s": bucket_s, "excluir_simulacoes": excluir_simulacoes})

    def exportar_csv(self, feature="dashboard-observabilidade") -> ApiResult:
        return self._get("/v1/observabilidade/export", feature)


def gerar_trafego_demo(base_url: str, n: int = 24) -> list[ApiResult]:
    """Dispara chamadas variadas (3 sessões, várias funcionalidades) para popular os
    indicadores. Inclui, de propósito: 1 chamada SEM headers, 1 TAG inválida e
    1 chamada com atraso injetado — para exercitar conformidade, 4xx e freshness."""
    tags = ["MT-001", "MT-002", "MT-003", "MT-004", "MT-005"]
    sessoes = [ApiClient(base_url, f"demo-{i}") for i in (1, 2, 3)]
    resultados: list[ApiResult] = []
    for i in range(n):
        c, tag = sessoes[i % 3], tags[i % len(tags)]
        if i % 3 == 0:
            resultados.append(c.leitura_atual(tag, feature="demo-leitura-atual"))
        elif i % 3 == 1:
            resultados.append(c.historico(tag, horas=24, feature="demo-historico"))
        else:
            resultados.append(c.leitura_atual(tag, feature="demo-visao-geral"))
    resultados.append(sessoes[0]._get("/v1/sensores/MT-001/leitura-atual", None, enviar_headers=False))
    resultados.append(sessoes[1].leitura_atual("XX-999", feature="demo-tag-invalida"))
    resultados.append(sessoes[2].leitura_atual("MT-001", feature="demo-atraso-injetado", simular_atraso_s=400))
    return resultados
