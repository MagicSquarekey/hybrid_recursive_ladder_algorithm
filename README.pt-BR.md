# Algoritmo de Escada Recursiva Híbrida (Hybrid Recursive Ladder Algorithm)

**Agregue intervalos longos de séries temporais com um punhado de requisições, em vez de milhares de consultas por bucket.**

**Idiomas / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.5-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23656844.svg)](https://doi.org/10.5281/zenodo.23656844)

<p align="center">
  <img src="docs/assets/hero.pt-BR.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>Mesma saída. Números de requisições muito diferentes.</em></p>

## O problema

A maioria das APIs de séries temporais cobra por requisição, por bucket ou por ida e volta. Uma implementação ingênua ("uma consulta por bucket estatístico") transforma um intervalo de dois dias em 2.880 buckets, cada um com até quatro chamadas HTTP. Em uma implantação real do ThingsBoard, 1.140 buckets levavam **139 segundos**.

O gargalo não é a aritmética: é o número de viagens de rede.

## A ideia

Divida `[start, end)` em **unidades de calendário completas**, de mês a minuto. Remova primeiro os meses completos; empurre as bordas parciais para o próximo nível mais fino; repita. Depois busque cada nível uma única vez usando a agregação do nível imediatamente mais fino e some localmente.

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

mês     2026-01 … 2026-09          9 segmentos
dia     10-01 … 10-20             20 segmentos
hora    10-21 00:00 … 17:00       18 segmentos
minuto  10-21 18:00 … 18:48       49 segmentos
cauda   10-21 18:49:00–18:49:59    1 segmento
                                  ────────────
                                  97 segmentos
```

**97 segmentos em vez de 423.049 buckets de minuto** (cerca de 4.360 vezes menos). Uma consulta típica de 10 meses precisa de **5–7 requisições de agregação**, não de milhares.

## Instalação

```bash
# v0.0.5 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.5/hybrid_recursive_ladder-0.0.5-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

Extras opcionais:

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

O núcleo de decomposição não tem dependências de terceiros (apenas `tzdata` para fusos IANA).

## Demo de 30 segundos

```bash
hybrid-ladder demo
```

Gera dados sintéticos a cada 15 minutos, decompõe 120 dias, materializa os primeiros 90 dias em um armazenamento em memória, executa uma consulta mista com prioridade local e verifica que os totais coincidem. Sem banco de dados, rede ou configuração.

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## Biblioteca

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 08:00
```

Com armazenamento local:

```python
from hybrid_ladder import LadderEngine
from hybrid_ladder.sources.thingsboard import ThingsBoardSource
from hybrid_ladder.stores.postgres import PostgresStore

source = ThingsBoardSource("https://tb.example.com", token="...")
store = PostgresStore("postgresql://user:pass@127.0.0.1:5432/telemetry")
engine = LadderEngine(source, store)

engine.materialize([("device-id", "energy")], start_ms, end_ms)
result = engine.sum_mixed([("device-id", "energy")], start_ms, end_ms)
print(result.source, result.source_counts, result.rows[0].tb_ranges)

report = engine.verify([("device-id", "energy")], start_ms, end_ms)
if report["diff_segments"]:
    engine.repair([("device-id", "energy")], start_ms, end_ms)
```

## Cinco formas de uso

| Forma | Ponto de entrada | Uso |
|---|---|---|
| Biblioteca Python | `from hybrid_ladder import ...` | integrar em serviço ou pipeline |
| CLI | `hybrid-ladder ...` | inspeção, scripts, cron |
| API HTTP | `hybrid-ladder serve` | integração multi-linguagem, tarefas assíncronas |
| Servidor MCP | `hybrid-ladder mcp` | agentes de IA / clientes MCP |
| Skill de agente | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | instalação como skill |

```bash
hybrid-ladder serve --port 8000     # OpenAPI: http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # servidor MCP via stdio
```

## Regras (não negociáveis)

1. **Intervalo fechado à esquerda e aberto à direita** `[start, end)`. Se o fim cair exatamente em um limite, essa unidade não existe no resultado.
2. **Somente unidades completas**. Mês/dia/hora/minuto só é emitido em seu nível se estiver inteiramente dentro do intervalo.
3. **Bordas recursivas**. Bordas parciais vão para o próximo nível mais fino; um resto menor que um minuto vira uma cauda própria.
4. **Calendário local**. Os limites usam o fuso IANA configurado (padrão `Asia/Shanghai`).
5. **Invariante de mosaico**. Os segmentos são ordenados, contíguos, sem sobreposição, e sua união é exatamente `[start, end)`.

## Semântica dos valores

| Valor | Significado | Exibição |
|---|---|---|
| `null` | sem amostras | `—` |
| `0.0` | há amostras e a soma é zero | `0` |
| número | soma das amostras | o número |

Cada segmento carrega `cnt` (pontos/buckets observados), `expected` (buckets esperados, apenas segmentos da fonte) e `source` (`local`, `tb`, `mixed`, `empty`, `uncovered`). Um `cnt` baixo em relação a `expected` indica dados esparsos; a soma continua correta para os pontos existentes, sem imputação.

## Adaptadores

O motor depende de duas interfaces estruturais mínimas:

```python
class TimeSeriesSource(Protocol):
    def interval_agg(ref, start_ms, end_ms, bucket_ms, agg="SUM") -> Mapping[int, Any]: ...
    def raw_series(ref, start_ms, end_ms, limit=10_000) -> list[tuple[int, Any]]: ...

class PointStore(Protocol):
    def sum_ranges(ref, ranges) -> Mapping[int, tuple[float | None, int]]: ...
    def series(ref, start_ms, end_ms, max_points=5_000) -> list[Mapping]: ...
    def coverage(ref) -> list[tuple[int, int, int]]: ...
    def delete_range(ref, start_ms, end_ms) -> int: ...
    def clear_coverage(ref, start_ms, end_ms) -> int: ...
    def upsert_points(ref, points, at_ms=None) -> int: ...
    def mark_covered(ref, start_ms, end_ms, point_cnt, at_ms) -> None: ...
```

Incluídos: `MemorySource` / `MemoryStore`, `ThingsBoardSource`, `PostgresStore`. InfluxDB, Prometheus ou ClickHouse só precisam desses métodos.

## Leitura local primeiro, verificação e reparo

* A cobertura só é registrada até `now - 5 minutos`; a cauda em andamento nunca é considerada local confiável.
* Um intervalo consultado é registrado mesmo com zero pontos ("consultamos, não há nada"), evitando consultas repetidas.
* Antes de reescrever um intervalo, sua cobertura é apagada: uma falha no meio do caminho não deixa cobertura apontando para dados incompletos.
* `verify` compara a fonte (autoridade) com o armazenamento local segmento a segmento e só desce a pontos (`added`/`removed`/`changed`) nos segmentos divergentes.
* `repair` apaga o intervalo local e o baixa novamente da fonte; pontos removidos na fonte desaparecem localmente.

## Limitações

* v0.0.5 implementa apenas `sum`. `avg` precisa de ponderação; `meter_delta` precisa do primeiro valor de cada segmento.
* Amostras ausentes fazem o total ficar menor que o total físico. `cnt/expected` evidenciam isso, mas não há imputação.
* O ThingsBoard aceita ~700 buckets e rejeita 800; o padrão é 500.
* Tarefas em segundo plano vivem na memória do processo e são perdidas no reinício (os resultados podem ser recalculados).
* Buckets de tamanho fixo fazem a dobra dia/hora ser pensada para fusos de offset fixo como `Asia/Shanghai`.

## Desempenho (medido)

| Cenário | Segmentos | Requisições | Tempo |
|---|---:|---:|---:|
| 2 dias, nível minuto | 69 | ~4 | 0,64 s |
| 1 ano, nível dia | 42 | ~4 | 1,18 s frio / 0,20 s quente |
| 10 meses, níveis mistos | 97 | ~5–7 | menos de 1 s |
| Leitura local | 42–90 | 0 | 9–19 ms |

Reproduza segmentos e requisições sem rede:

```bash
python examples/benchmark.py
```

## Documentação

* [Especificação do algoritmo](docs/algorithm.md)
* [Arquitetura](docs/architecture.md)
* [Referência da API](docs/api.md)
* [Benchmarks](docs/benchmarks.md)
* [Trabalhos relacionados e posicionamento](docs/related-work.md)

## Licença

[MIT](LICENSE) © 2026 MagicSquarekey
