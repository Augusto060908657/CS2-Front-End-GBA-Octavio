# Forzy · Digital Twin — Sensor Monitoring API + Dashboard
**Checkpoint integrado: Governança em IA × Front-End** — *Observabilidade de um endpoint de IA*

Link do Video Youtube - [Video](https://youtu.be/G1lprYYuC-I)

API **FastAPI** do provider de Sensores (leitura atual e histórico) com **registro de observabilidade a cada chamada**,
consumida por uma interface **Streamlit** via `requests`.

## Integrantes
| Nome | RM |
|---|---|
| Octávio … | 555696 |

Repositório: _[[link do GitHub](https://github.com/Augusto060908/CS-2-Front-End-Octavio.git)]_

## Arquitetura
```
Streamlit (frontend/)  ──requests + headers X-Session-Id / X-Feature──▶  FastAPI (backend/)
                                                                          │ middleware de observabilidade
                                                                          ▼
                                                                  SQLite (backend/data/observabilidade.db)
```

## Como rodar
Requer Python 3.10+. Na **raiz do projeto**:
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

# Terminal 1 — API  (docs interativas em http://127.0.0.1:8000/docs)
uvicorn backend.main:app --port 8000

# Terminal 2 — Interface (abre em http://localhost:8501)
streamlit run frontend/app.py
```
Para usar outra URL de API: `set API_BASE_URL=http://host:porta` (ou campo "URL da API" na barra lateral).

**Dica para a demonstração:** na página *Observabilidade*, clique em **🧪 Gerar tráfego de demonstração** para popular os registros.
Para zerar os registros, pare a API e apague `backend/data/observabilidade.db`.

## Endpoints
| Funcionalidade | Endpoint | Tela do front |
|---|---|---|
| Catálogo | `GET /v1/sensores` | seletor Planta → Linha → TAG |
| Leitura atual | `GET /v1/sensores/{tag}/leitura-atual` | **Leitura Atual** (leitura + severidade + freshness) |
| Histórico | `GET /v1/sensores/{tag}/historico?horas=&intervalo_min=` | **Histórico** (gráficos, tabela, completude) |
| Observabilidade | `GET /v1/observabilidade` (filtros: `feature`, `session_id`, `tag`, `endpoint`, `status_code`) | **Observabilidade** (registros brutos) |
| Indicadores | `GET /v1/observabilidade/indicadores` | **Observabilidade** (contrato + gráficos) |
| Exportação | `GET /v1/observabilidade/export` | CSV dos registros |

## O que é registrado em cada chamada (`/v1/*`)
`request_id`, `timestamp` (UTC), **`session_id`** (header `X-Session-Id`), **`feature`** (header `X-Feature`), método, endpoint
(rota e caminho), `tag`, `status_code`, **`latencia_ms`**, `contexto_completo` (ambos os headers presentes?),
`freshness_s` (idade do dado), `completude_pct` (pontos retornados ÷ esperados), `severidade`, `registros_retornados`, `simulacao`.

O front envia `X-Session-Id` (único por sessão do navegador) e `X-Feature` (`dashboard-leitura-atual`,
`dashboard-historico`, `dashboard-observabilidade`, …) em **todas** as chamadas — ver `frontend/api_client.py`.
A API também devolve `X-Request-Id` e `X-Process-Time-Ms` nas respostas.

## Contrato de métricas (Metric Contract)
Seis indicadores com baseline, limiares, camada gráfica e ação em caso de estouro — definidos em `backend/config.py`
e resumidos em [`docs/Metric_Contract.md`](docs/Metric_Contract.md). Os valores são uma proposta inicial:
**alinhe-os ao relatório de Governança** antes de entregar.

## Injeção de falhas (apenas demonstração)
Para evidenciar o estouro de limiares, a barra lateral tem **🧪 Injeção de falhas**, e a API aceita (`/docs`):
`simular_atraso_s` (freshness), `simular_falhas` (completude), `simular_latencia_ms` e `simular_erro` (HTTP 500).
Esses registros ficam marcados na coluna `simulacao` e podem ser ignorados nos indicadores (`excluir_simulacoes=true`).
Chamadas **sem headers** (conformidade) podem ser vistas com `python scripts/consumir_api.py trafego`.

## Script de consumo via `requests`
```bash
python scripts/consumir_api.py tudo                 # fluxo completo
python scripts/consumir_api.py leitura MT-001
python scripts/consumir_api.py historico MT-002 --horas 24
python scripts/consumir_api.py observabilidade --limite 10
python scripts/consumir_api.py indicadores --janela 60
python scripts/consumir_api.py trafego -n 30        # gera tráfego de demonstração
```

## Testes
```bash
pip install -r requirements-dev.txt
pytest -q
```

## Estrutura
```
backend/   main.py (rotas + middleware) · provider.py · observability.py · registry.py · config.py
frontend/  app.py (Leitura Atual) · pages/1_Historico.py · pages/2_Observabilidade.py · api_client.py · charts.py · common.py · theme.py
scripts/   consumir_api.py
tests/     test_api.py
docs/      Metric_Contract.md
```

## Observações
- Os dados dos sensores são **simulados e determinísticos** (mesma TAG + mesmo instante = mesmo valor). Para dados reais,
  substitua `leitura_atual()` e `historico()` em `backend/provider.py`.
- Sem autenticação e sem providers de Equipamentos/Plantas (fora do escopo do checkpoint).
- Parte do código foi desenvolvida com apoio de IA generativa (Claude); declare isso no tópico "Uso de IA" do relatório.
