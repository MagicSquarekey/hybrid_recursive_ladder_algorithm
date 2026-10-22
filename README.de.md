# Hybrider rekursiver Leiter-Algorithmus (Hybrid Recursive Ladder Algorithm)

**Lange Zeitreihenbereiche mit einer Handvoll Quellanfragen aggregieren statt mit Tausenden Abfragen pro Bucket.**

**Sprachen / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.4-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23556606.svg)](https://doi.org/10.5281/zenodo.23556606)

<p align="center">
  <img src="docs/assets/hero.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>Gleiche Ausgabe. Sehr unterschiedliche Anforderungszahlen.</em></p>

## Das Problem

Die meisten Zeitreihen-APIs berechnen nach Anfragen, Buckets oder Roundtrips. Eine naive Implementierung („eine Abfrage pro statistischem Bucket") macht aus einem Zwei-Tage-Bereich auf Minutenebene 2.880 Buckets, jeder mit bis zu vier HTTP-Aufrufen. In einer produktiven ThingsBoard-Umgebung dauerten 1.140 Buckets **139 Sekunden**.

Der Engpass ist nicht die Arithmetik, sondern die Anzahl der Netzwerk-Roundtrips.

## Die Idee

`[start, end)` wird in **vollständige Kalendereinheiten** zerlegt, von Monat bis Minute. Vollständige Monate werden zuerst abgetragen; die partiellen Ränder wandern eine Ebene tiefer; am feinsten Level wird ein Rest unter einer Minute zu einem eigenen „Tail"-Segment. Jede Ebene wird anschließend einmal mit der Aggregation der nächstfeineren Ebene abgerufen und lokal aufsummiert.

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

Monat   2026-01 … 2026-09          9 Segmente
Tag     10-01 … 10-20             20 Segmente
Stunde  10-21 00:00 … 17:00       18 Segmente
Minute  10-21 18:00 … 18:48       49 Segmente
Rest    10-21 18:49:00–18:49:59    1 Segment
                                  ───────────
                                  97 Segmente
```

**97 Segmente statt 423.049 Minuten-Buckets** (etwa 4.360-mal weniger). Eine typische 10-Monats-Abfrage braucht **5–7 Aggregationsanfragen**, nicht Tausende.

## Installation

```bash
# v0.0.4 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.4/hybrid_recursive_ladder-0.0.4-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

Optionale Extras:

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

Der Kern hat keine Drittanbieter-Abhängigkeiten (nur `tzdata` für IANA-Zeitzonen).

## 30-Sekunden-Demo

```bash
hybrid-ladder demo
```

Erzeugt synthetische 15-Minuten-Daten, zerlegt 120 Tage, materialisiert die ersten 90 Tage in einen In-Memory-Store, führt eine gemischte „lokal zuerst"-Abfrage aus und prüft, dass die Summen übereinstimmen. Ohne Datenbank, Netzwerk oder Konfiguration.

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## Bibliothek

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 08:00
```

Mit lokalem Store:

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

## Fünf Nutzungsformen

| Form | Einstieg | Einsatz |
|---|---|---|
| Python-Bibliothek | `from hybrid_ladder import ...` | Einbettung in Services/Pipelines |
| CLI | `hybrid-ladder ...` | Analyse, Skripte, Cron |
| HTTP-API | `hybrid-ladder serve` | sprachunabhängige Integration, Async-Tasks |
| MCP-Server | `hybrid-ladder mcp` | KI-Agenten / MCP-Clients |
| Agent-Skill | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | Installation als Skill |

```bash
hybrid-ladder serve --port 8000     # OpenAPI: http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # MCP-Server über stdio
```

## Regeln (nicht verhandelbar)

1. **Links geschlossen, rechts offen** `[start, end)`. Liegt das Ende genau auf einer Grenze, existiert diese Einheit nicht im Ergebnis.
2. **Nur vollständige Einheiten**. Monat/Tag/Stunde/Minute werden nur dann auf ihrer Ebene ausgegeben, wenn sie vollständig im Bereich liegen.
3. **Ränder rekursiv**. Partielle linke/rechte Ränder wandern eine Ebene tiefer; ein Rest unter einer Minute wird ein eigener Tail.
4. **Lokaler Kalender**. Grenzen verwenden die konfigurierte IANA-Zeitzone (Standard `Asia/Shanghai`).
5. **Kachel-Invariante**. Segmente sind geordnet, zusammenhängend, überlappungsfrei und ihre Vereinigung ist exakt `[start, end)`.

## Wertsemantik

| Wert | Bedeutung | Anzeige |
|---|---|---|
| `null` | keine Messwerte | `—` |
| `0.0` | Messwerte vorhanden, Summe null | `0` |
| Zahl | Summe der Messwerte | die Zahl |

Jedes Segment trägt `cnt` (beobachtete Punkte/Buckets), `expected` (erwartete Buckets, nur Quellsegmente) und `source` (`local`, `tb`, `mixed`, `empty`, `uncovered`). Ein niedriges `cnt` gegenüber `expected` zeigt dünne Daten an; die Summe bleibt für die vorhandenen Punkte korrekt, es wird nichts interpoliert.

## Adapter

Der Motor hängt nur von zwei kleinen strukturellen Schnittstellen ab:

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

Enthalten: `MemorySource` / `MemoryStore`, `ThingsBoardSource`, `PostgresStore`. InfluxDB, Prometheus oder ClickHouse brauchen nur diese Methoden.

## Lokal zuerst, Prüfen und Reparieren

* Abdeckung wird nur bis `now - 5 Minuten` registriert; der laufende Tail gilt nie als verlässlich lokal.
* Ein abgefragter Bereich wird auch bei null Punkten als „geprüft" registriert, damit er nicht erneut abgefragt wird.
* Vor dem Neuschreiben eines Bereichs wird seine Abdeckung gelöscht: Ein halber Fehlschlag hinterlässt keine Abdeckung, die auf unvollständige Daten zeigt.
* `verify` vergleicht die Quelle (Autorität) segmentweise mit dem lokalen Store und geht nur bei abweichenden Segmenten auf Punktebene (`added`/`removed`/`changed`).
* `repair` löscht den lokalen Bereich und lädt ihn erneut aus der Quelle; dort gelöschte Punkte verschwinden lokal.

## Grenzen

* v0.0.4 implementiert nur `sum`. `avg` braucht Gewichtung; `meter_delta` braucht den ersten Wert jedes Segments.
* Fehlende Messwerte machen die Summe kleiner als die physische Gesamtsumme. `cnt/expected` zeigt das an, es wird nichts interpoliert.
* ThingsBoard akzeptiert ca. 700 Buckets und lehnt 800 ab; Standard ist 500.
* Hintergrundtasks liegen im Prozessspeicher und gehen beim Neustart verloren (Ergebnisse sind neu berechenbar).
* Wegen fester Bucket-Größen ist die Tag/Stunde-Faltung für Zeitzonen mit festem Offset wie `Asia/Shanghai` ausgelegt.

## Leistung (gemessen)

| Szenario | Segmente | Anfragen | Zeit |
|---|---:|---:|---:|
| 2 Tage, Minutenebene | 69 | ~4 | 0,64 s |
| 1 Jahr, Tagesebene | 42 | ~4 | 1,18 s kalt / 0,20 s warm |
| 10 Monate, gemischt | 97 | ~5–7 | unter 1 s |
| Lokales Lesen | 42–90 | 0 | 9–19 ms |

Segmente und Anfragen ohne Netzwerk reproduzieren:

```bash
python examples/benchmark.py
```

## Dokumentation

* [Algorithmus-Spezifikation](docs/algorithm.md)
* [Architektur](docs/architecture.md)
* [API-Referenz](docs/api.md)
* [Benchmarks](docs/benchmarks.md)
* [Verwandte Arbeiten und Positionierung](docs/related-work.md)

## Lizenz

[MIT](LICENSE) © 2026 MagicSquarekey
