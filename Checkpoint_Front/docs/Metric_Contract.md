# Metric Contract — valores implementados no código

> Gerado a partir de `backend/config.py`. Se alterar limiares no relatório, altere também no `config.py` (e vice-versa) para manter código e documento consistentes.

| Indicador | Fórmula | Baseline | Atenção | Crítico | Camada gráfica |
|---|---|---|---|---|---|
| Freshness (idade do dado) — p95 | `p95( timestamp_da_chamada − timestamp_da_medição ) nas chamadas de leitura-atual` | 60 s | > 120 s | > 300 s | Gráfico de linha (série temporal por chamada) com linhas de limiar |
| Taxa de completude de Freshness | `leituras com freshness ≤ 120s ÷ total de leituras × 100` | 98 % | < 95 % | < 90 % | Gráfico de linha da taxa por janela de tempo |
| Completude do histórico | `pontos_retornados ÷ pontos_esperados × 100 (média nas chamadas de historico)` | 98 % | < 95 % | < 90 % | Gráfico de linha com marcadores; lacunas visíveis nas séries do histórico |
| Latência da API — p95 | `p95( latencia_ms ) nas chamadas aos endpoints de sensores` | 120 ms | > 300 ms | > 800 ms | Gráfico de linha (latência por chamada) com linhas de limiar |
| Taxa de erro do servidor (5xx) | `chamadas com status ≥ 500 ÷ total de chamadas × 100` | 0 % | > 1 % | > 5 % | Barras empilhadas por classe de status (2xx/4xx/5xx) ao longo do tempo |
| Conformidade dos headers de contexto | `chamadas com ambos os headers ÷ total de chamadas × 100` | 100 % | < 99 % | < 95 % | Gauge (indicador de ponteiro) com faixas de limiar |

## Ações quando o limiar é estourado

### Freshness (idade do dado) — p95
- **Atenção:** Verificar conectividade do gateway/broker do sensor e abrir ticket para a equipe de dados.
- **Crítico:** Marcar a leitura como obsoleta no front, notificar o responsável pelo ativo e acionar contingência de coleta manual.

### Taxa de completude de Freshness
- **Atenção:** Investigar quais TAGs concentram atrasos e revisar a frequência de coleta.
- **Crítico:** Escalar ao time de plataforma, congelar decisões automáticas que dependam do dado e reportar à Governança.

### Completude do histórico
- **Atenção:** Listar as lacunas por TAG e verificar falhas intermitentes de coleta.
- **Crítico:** Sinalizar o histórico como incompleto em relatórios/modelos e abrir incidente de qualidade de dados.

### Latência da API — p95
- **Atenção:** Analisar as chamadas mais lentas por endpoint/funcionalidade e revisar consultas e carga.
- **Crítico:** Escalar para o time de back-end, ativar cache/limite de janela do histórico e avaliar escalar o serviço.

### Taxa de erro do servidor (5xx)
- **Atenção:** Inspecionar os registros com erro (endpoint, TAG, funcionalidade) e corrigir a causa-raiz.
- **Crítico:** Abrir incidente, considerar rollback da última versão e comunicar os consumidores do endpoint.

### Conformidade dos headers de contexto
- **Atenção:** Identificar o cliente que não envia os headers e orientar a correção.
- **Crítico:** Passar a rejeitar (HTTP 400) chamadas sem contexto e tratar a lacuna como falha de auditabilidade.
