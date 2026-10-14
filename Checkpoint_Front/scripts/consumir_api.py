"""
scripts/consumir_api.py — consome a API via `requests` (sem interface gráfica).

Exemplos (a partir da raiz do projeto, com a API rodando):
    python scripts/consumir_api.py leitura MT-001
    python scripts/consumir_api.py historico MT-002 --horas 24
    python scripts/consumir_api.py observabilidade --limite 10
    python scripts/consumir_api.py indicadores --janela 60
    python scripts/consumir_api.py tudo            # roda um fluxo completo
    python scripts/consumir_api.py trafego -n 30   # gera tráfego de demonstração
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
from api_client import ApiClient, gerar_trafego_demo  # noqa: E402


def mostrar(r, titulo):
    print(f"\n=== {titulo} ===\n{r.resumo()}")
    if r.data is not None:
        print(json.dumps(r.data, indent=2, ensure_ascii=False)[:2500])
    elif r.erro:
        print("Erro:", r.erro)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    p.add_argument("--session", default="script-consumo", help="valor do header X-Session-Id")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sensores")
    s = sub.add_parser("leitura"); s.add_argument("tag")
    s = sub.add_parser("historico"); s.add_argument("tag"); s.add_argument("--horas", type=int, default=24); s.add_argument("--intervalo", type=int, default=30)
    s = sub.add_parser("observabilidade"); s.add_argument("--limite", type=int, default=10)
    s = sub.add_parser("indicadores"); s.add_argument("--janela", type=int, default=60)
    sub.add_parser("tudo")
    s = sub.add_parser("trafego"); s.add_argument("-n", type=int, default=24)
    a = p.parse_args()

    c = ApiClient(a.url, a.session)
    if not c.health().ok:
        sys.exit(f"API indisponível em {a.url}. Inicie com: uvicorn backend.main:app --port 8000")

    f = "script-consumo"
    if a.cmd == "sensores":
        mostrar(c.sensores(f), "Catálogo")
    elif a.cmd == "leitura":
        mostrar(c.leitura_atual(a.tag, f), f"Leitura atual {a.tag}")
    elif a.cmd == "historico":
        r = c.historico(a.tag, a.horas, a.intervalo, f)
        if r.data:
            r.data["pontos"] = r.data["pontos"][:3] + ["... (resumido)"]
        mostrar(r, f"Histórico {a.tag}")
    elif a.cmd == "observabilidade":
        mostrar(c.observabilidade(f, limite=a.limite), "Registros de observabilidade")
    elif a.cmd == "indicadores":
        r = c.indicadores(a.janela, feature=f)
        print(r.resumo())
        for i in r.data["indicadores"]:
            print(f"- {i['nome']}: {i['valor']} {i['unidade']}  [{i['status']}]")
    elif a.cmd == "tudo":
        mostrar(c.sensores(f), "Catálogo")
        mostrar(c.leitura_atual("MT-001", f), "Leitura atual MT-001")
        r = c.historico("MT-001", 24, 30, f)
        print("\n=== Histórico MT-001 ===\n" + r.resumo(), f"\ncompletude: {r.data['completude_pct']}%")
        mostrar(c.observabilidade(f, limite=3), "Últimos 3 registros")
    elif a.cmd == "trafego":
        res = gerar_trafego_demo(a.url, a.n)
        print(f"{len(res)} chamadas disparadas; {sum(r.ok for r in res)} OK.")


if __name__ == "__main__":
    main()
