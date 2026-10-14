"""Testes da API: rodar com `pytest -q` na raiz do projeto."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["OBS_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "obs_test.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)
H = {"X-Session-Id": "sess-teste", "X-Feature": "teste-unitario"}


def ultimo_registro(**filtros):
    return client.get("/v1/observabilidade", params={"limite": 1, **filtros}).json()["registros"][0]


def test_catalogo_e_health():
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/v1/sensores", headers=H).json()
    assert r["total"] == 5 and r["sensores"][0]["tag"] == "MT-001"


def test_leitura_atual_registra_contexto():
    r = client.get("/v1/sensores/MT-001/leitura-atual", headers=H)
    assert r.status_code == 200
    d = r.json()
    assert d["severidade"] == "ok" and d["freshness_s"] > 0 and "X-Request-Id" in r.headers
    reg = ultimo_registro(tag="MT-001")
    assert reg["session_id"] == "sess-teste" and reg["feature"] == "teste-unitario"
    assert reg["endpoint"] == "/v1/sensores/{tag}/leitura-atual" and reg["status_code"] == 200
    assert reg["latencia_ms"] > 0 and reg["contexto_completo"] is True and reg["timestamp"].endswith("Z")


def test_sem_headers_marca_nao_conformidade():
    client.get("/v1/sensores/MT-003/leitura-atual")
    reg = ultimo_registro(tag="MT-003")
    assert reg["contexto_completo"] is False and reg["session_id"] is None


def test_tag_invalida_404_registrado():
    assert client.get("/v1/sensores/XX-999/leitura-atual", headers=H).status_code == 404
    assert ultimo_registro(tag="XX-999")["status_code"] == 404


def test_historico_completude():
    d = client.get("/v1/sensores/MT-001/historico", params={"horas": 24, "intervalo_min": 30}, headers=H).json()
    assert d["pontos_esperados"] == 48 and d["pontos_retornados"] == len(d["pontos"])
    assert 0 < d["completude_pct"] <= 100
    d2 = client.get("/v1/sensores/MT-001/historico", params={"simular_falhas": 0.5}, headers=H).json()
    assert d2["completude_status"] == "crit"


def test_validacao_422():
    assert client.get("/v1/sensores/MT-001/historico", params={"horas": 9999}, headers=H).status_code == 422


def test_erro_simulado_5xx():
    assert client.get("/v1/sensores/MT-002/leitura-atual", params={"simular_erro": True}, headers=H).status_code == 500
    reg = ultimo_registro(tag="MT-002")
    assert reg["status_code"] == 500 and "erro" in reg["simulacao"]


def test_atraso_simulado_estoura_freshness():
    d = client.get("/v1/sensores/MT-005/leitura-atual", params={"simular_atraso_s": 600}, headers=H).json()
    assert d["freshness_status"] == "crit"


def test_indicadores_e_export():
    ind = client.get("/v1/observabilidade/indicadores", params={"janela_min": 60}).json()
    ids = {i["id"] for i in ind["indicadores"]}
    assert {"freshness_p95_s", "latencia_p95_ms", "conformidade_headers", "taxa_erro_5xx"} <= ids
    conf = next(i for i in ind["indicadores"] if i["id"] == "conformidade_headers")
    assert conf["valor"] < 100 and conf["status"] in ("warn", "crit")   # houve chamada sem headers
    assert ind["total_chamadas"] > 0 and ind["series"]
    csv = client.get("/v1/observabilidade/export")
    assert csv.headers["content-type"].startswith("text/csv") and "request_id" in csv.text.splitlines()[0]
