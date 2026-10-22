# Algorithme d'Échelle Récursive Hybride (Hybrid Recursive Ladder Algorithm)

**Agrégez de longues plages de séries temporelles en quelques requêtes au lieu de milliers de requêtes par compartiment.**

**Langues / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.3-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23556606.svg)](https://doi.org/10.5281/zenodo.23556606)

<p align="center">
  <img src="docs/assets/hero.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>Même sortie. Deux nombres de requêtes très différents.</em></p>

## Le problème

La plupart des API de séries temporelles facturent par requête, par compartiment ou par aller-retour. Une implémentation naïve (« une requête par compartiment statistique ») transforme une plage de deux jours au niveau minute en 2 880 compartiments, chacun nécessitant jusqu'à quatre appels HTTP. Sur un déploiement ThingsBoard réel, 1 140 compartiments prenaient **139 secondes**.

Le goulot d'étranglement n'est pas le calcul : c'est le nombre d'allers-retours réseau.

## L'idée

Découper `[start, end)` en **unités calendaires complètes**, du mois à la minute. On retire d'abord les mois complets ; les bords partiels sont poussés au niveau plus fin ; on répète. Chaque niveau est ensuite récupéré une seule fois avec l'agrégation du niveau immédiatement plus fin, puis sommé localement.

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

mois    2026-01 … 2026-09          9 segments
jour    10-01 … 10-20             20 segments
heure   10-21 00:00 … 17:00       18 segments
minute  10-21 18:00 … 18:48       49 segments
reste   10-21 18:49:00–18:49:59    1 segment
                                  ───────────
                                  97 segments
```

**97 segments au lieu de 423 049 compartiments minute** (environ 4 360 fois moins). Une requête typique de 10 mois nécessite **5 à 7 requêtes d'agrégation**, pas des milliers.

## Installation

```bash
# v0.0.3 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.3/hybrid_recursive_ladder-0.0.3-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

Extensions optionnelles :

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

Le cœur de décomposition n'a aucune dépendance tierce (seulement `tzdata` pour les fuseaux IANA).

## Démo en 30 secondes

```bash
hybrid-ladder demo
```

Génère des données synthétiques toutes les 15 minutes, décompose 120 jours, matérialise les 90 premiers jours dans un stockage mémoire, exécute une requête mixte « local d'abord » et vérifie que les totaux concordent. Sans base de données, réseau ni configuration.

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## Bibliothèque

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 08:00
```

Avec un stockage local :

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

## Cinq modes d'utilisation

| Forme | Point d'entrée | Usage |
|---|---|---|
| Bibliothèque Python | `from hybrid_ladder import ...` | intégration dans un service ou un pipeline |
| CLI | `hybrid-ladder ...` | inspection, scripts, cron |
| API HTTP | `hybrid-ladder serve` | intégration multi-langages, tâches asynchrones |
| Serveur MCP | `hybrid-ladder mcp` | agents IA / clients MCP |
| Skill d'agent | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | installation comme skill |

```bash
hybrid-ladder serve --port 8000     # OpenAPI : http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # serveur MCP stdio
```

## Règles (non négociables)

1. **Intervalle fermé à gauche, ouvert à droite** `[start, end)`. Si la fin tombe exactement sur une limite, cette unité n'existe pas dans le résultat.
2. **Unités complètes uniquement**. Un mois/jour/heure/minute n'est émis à son niveau que s'il est entièrement contenu dans la plage.
3. **Bords récursifs**. Les bords partiels passent au niveau plus fin ; un reste inférieur à une minute devient un segment de queue.
4. **Calendrier local**. Les limites utilisent le fuseau IANA configuré (par défaut `Asia/Shanghai`).
5. **Invariant de pavage**. Les segments sont ordonnés, contigus, sans chevauchement, et leur union vaut exactement `[start, end)`.

## Sémantique des valeurs

| Valeur | Signification | Affichage |
|---|---|---|
| `null` | aucune mesure | `—` |
| `0.0` | des mesures existent et somment à zéro | `0` |
| nombre | somme des mesures | le nombre |

Chaque segment porte `cnt` (points/compartiments observés), `expected` (compartiments attendus, source uniquement) et `source` (`local`, `tb`, `mixed`, `empty`, `uncovered`). Un `cnt` faible par rapport à `expected` signale des données éparses ; la somme reste correcte pour les points existants, sans imputation.

## Adaptateurs

Le moteur dépend de deux interfaces structurelles minimales :

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

Inclus : `MemorySource` / `MemoryStore`, `ThingsBoardSource`, `PostgresStore`. InfluxDB, Prometheus ou ClickHouse n'ont besoin que de ces méthodes.

## Lecture locale d'abord, vérification et réparation

* La couverture n'est enregistrée que jusqu'à `now - 5 minutes` ; la queue en cours n'est jamais considérée comme locale fiable.
* Une plage interrogée est enregistrée même avec zéro point (« on a demandé, il n'y a rien »), ce qui évite les requêtes répétées.
* Avant de réécrire une plage, sa couverture est effacée : un échec en cours de route ne laisse pas de couverture pointant vers des données incomplètes.
* `verify` compare la source (autorité) au stockage local segment par segment et ne descend au niveau des points (`added`/`removed`/`changed`) que pour les segments divergents.
* `repair` supprime la plage locale et la retélécharge depuis la source ; les points supprimés à la source disparaissent localement.

## Limites

* v0.0.3 n'implémente que `sum`. `avg` nécessite une pondération ; `meter_delta` nécessite la première valeur de chaque segment.
* Des mesures manquantes rendent le total inférieur au total physique. `cnt/expected` le signalent, sans imputation.
* ThingsBoard accepte environ 700 compartiments et en refuse 800 ; la valeur par défaut est 500.
* Les tâches d'arrière-plan vivent en mémoire du processus et sont perdues au redémarrage (les résultats sont recalculables).
* Les compartiments de taille fixe font que le repliement jour/heure est conçu pour les fuseaux à décalage fixe comme `Asia/Shanghai`.

## Performances (mesurées)

| Scénario | Segments | Requêtes | Temps |
|---|---:|---:|---:|
| 2 jours, niveau minute | 69 | ~4 | 0,64 s |
| 1 an, niveau jour | 42 | ~4 | 1,18 s à froid / 0,20 s à chaud |
| 10 mois, niveaux mixtes | 97 | ~5–7 | moins d'une seconde |
| Lecture locale | 42–90 | 0 | 9–19 ms |

Reproduire les segments et les requêtes sans réseau :

```bash
python examples/benchmark.py
```

## Documentation

* [Spécification de l'algorithme](docs/algorithm.md)
* [Architecture](docs/architecture.md)
* [Référence API](docs/api.md)
* [Performances](docs/benchmarks.md)
* [Travaux connexes et positionnement](docs/related-work.md)

## Licence

[MIT](LICENSE) © 2026 MagicSquarekey
