# Algoritmo de Escalera Recursiva Híbrida (Hybrid Recursive Ladder Algorithm)

**Agrega rangos largos de series temporales con un puñado de peticiones, en lugar de miles de consultas por bucket.**

**Idiomas / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.4-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23556606.svg)](https://doi.org/10.5281/zenodo.23556606)

<p align="center">
  <img src="docs/assets/hero.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>Misma salida. Números de solicitudes muy distintos.</em></p>

## El problema

La mayoría de las API de series temporales cobran por petición, por bucket o por ida y vuelta. Una implementación ingenua ("una consulta por cada bucket estadístico") convierte un rango de dos días en 2.880 buckets, cada uno con hasta cuatro llamadas HTTP. En un despliegue real de ThingsBoard, 1.140 buckets tardaban **139 segundos**.

El cuello de botella no es la aritmética: es el número de viajes de red.

## La idea

Divide `[start, end)` en **unidades de calendario completas**, de mes a minuto. Separa primero los meses completos; empuja los bordes parciales al siguiente nivel más fino; repite. Después obtén cada nivel una sola vez usando la agregación del nivel inmediatamente más fino y suma localmente.

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

mes    2026-01 … 2026-09          9 segmentos
día    10-01 … 10-20             20 segmentos
hora   10-21 00:00 … 17:00       18 segmentos
minuto 10-21 18:00 … 18:48       49 segmentos
cola   10-21 18:49:00–18:49:59    1 segmento
                                 ────────────
                                 97 segmentos
```

**97 segmentos en lugar de 423.049 buckets de minuto** (unas 4.360 veces menos). Una consulta típica de 10 meses necesita **5–7 peticiones de agregación**, no miles.

## Instalación

```bash
# v0.0.4 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.4/hybrid_recursive_ladder-0.0.4-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

Extras opcionales:

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

El núcleo de descomposición no tiene dependencias de terceros (solo `tzdata` para zonas horarias IANA).

## Demo de 30 segundos

```bash
hybrid-ladder demo
```

Genera datos sintéticos cada 15 minutos, descompone 120 días, materializa los primeros 90 días en un almacén en memoria, ejecuta una consulta mixta con prioridad local y verifica que los totales coincidan. Sin base de datos, red ni configuración.

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

Con almacén local:

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

| Forma | Punto de entrada | Uso |
|---|---|---|
| Biblioteca Python | `from hybrid_ladder import ...` | integrar en un servicio o pipeline |
| CLI | `hybrid-ladder ...` | inspección, scripts, cron |
| API HTTP | `hybrid-ladder serve` | integración multi-lenguaje, tareas asíncronas |
| Servidor MCP | `hybrid-ladder mcp` | agentes de IA / clientes MCP |
| Skill de agente | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | instalación como skill |

```bash
hybrid-ladder serve --port 8000     # OpenAPI: http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # servidor MCP por stdio
```

## Reglas (no negociables)

1. **Intervalo cerrado a la izquierda y abierto a la derecha** `[start, end)`. Si el final cae exactamente en un límite, esa unidad no existe en el resultado.
2. **Solo unidades completas**. Un mes/día/hora/minuto se emite en su nivel solo si está completamente dentro del rango.
3. **Bordes recursivos**. Los bordes parciales pasan al siguiente nivel más fino; un resto menor a un minuto se convierte en una cola propia.
4. **Calendario local**. Los límites usan la zona IANA configurada (por defecto `Asia/Shanghai`).
5. **Invariante de mosaico**. Los segmentos son ordenados, contiguos, no se solapan y su unión es exactamente `[start, end)`.

## Semántica de valores

| Valor | Significado | Se muestra como |
|---|---|---|
| `null` | no hay muestras | `—` |
| `0.0` | hay muestras y suman cero | `0` |
| número | suma de las muestras | el número |

Cada segmento lleva `cnt` (puntos/buckets observados), `expected` (buckets que debería contener, solo segmentos de la fuente) y `source` (`local`, `tb`, `mixed`, `empty`, `uncovered`). Un `cnt` bajo respecto de `expected` indica datos dispersos; la suma sigue siendo correcta para los puntos existentes, pero no se imputan datos.

## Adaptadores

El motor depende de dos interfaces estructurales mínimas:

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

Incluidos: `MemorySource` / `MemoryStore`, `ThingsBoardSource`, `PostgresStore`. InfluxDB, Prometheus o ClickHouse solo necesitan esos métodos.

## Lectura local primero, verificación y reparación

* La cobertura solo se registra hasta `now - 5 minutos`; la cola en curso nunca se considera local fiable.
* Un rango consultado se registra aunque tenga cero puntos ("ya preguntamos, no hay nada"), evitando consultas repetidas.
* Antes de reescribir un rango se borra su cobertura: si la descarga falla a medias, no queda cobertura apuntando a datos incompletos.
* `verify` compara la fuente (autoridad) con el almacén local por segmento y solo desciende a puntos (`added`/`removed`/`changed`) en los segmentos con diferencias.
* `repair` borra el rango local y lo vuelve a descargar de la fuente; los puntos eliminados en la fuente desaparecen localmente.

## Limitaciones

* v0.0.4 solo implementa `sum`. `avg` requiere ponderación; `meter_delta` requiere el primer valor de cada segmento.
* Si faltan muestras, el total será menor que el total físico. `cnt/expected` lo evidencian, pero no se imputan datos.
* ThingsBoard acepta ~700 buckets y rechaza 800; el valor por defecto es 500.
* Las tareas en segundo plano viven en memoria del proceso y se pierden al reiniciar (los resultados se pueden recalcular).
* Los buckets de tamaño fijo hacen que el plegado día/hora esté pensado para zonas de offset fijo como `Asia/Shanghai`.

## Rendimiento (medido)

| Escenario | Segmentos | Peticiones | Tiempo |
|---|---:|---:|---:|
| 2 días, nivel minuto | 69 | ~4 | 0,64 s |
| 1 año, nivel día | 42 | ~4 | 1,18 s en frío / 0,20 s en caliente |
| 10 meses, niveles mixtos | 97 | ~5–7 | menos de 1 s |
| Lectura local | 42–90 | 0 | 9–19 ms |

Reproduce segmentos y peticiones sin red:

```bash
python examples/benchmark.py
```

## Documentación

* [Especificación del algoritmo](docs/algorithm.md)
* [Arquitectura](docs/architecture.md)
* [Referencia de API](docs/api.md)
* [Rendimiento](docs/benchmarks.md)
* [Trabajo relacionado y posicionamiento](docs/related-work.md)

## Licencia

[MIT](LICENSE) © 2026 MagicSquarekey
