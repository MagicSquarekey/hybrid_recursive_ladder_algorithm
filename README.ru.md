# Гибридный рекурсивный лестничный алгоритм (Hybrid Recursive Ladder Algorithm)

**Агрегируйте длинные диапазоны временных рядов несколькими запросами вместо тысяч запросов по бакетам.**

**Языки / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.4-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23557574.svg)](https://doi.org/10.5281/zenodo.23557574)

<p align="center">
  <img src="docs/assets/hero.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>Тот же результат. Совершенно разное число запросов.</em></p>

## Проблема

Большинство API временных рядов берут плату за запрос, за бакет или за сетевой обмен. Наивная реализация («один запрос на каждый статистический бакет») превращает двухдневный диапазон с минутной детализацией в 2 880 бакетов, каждому из которых нужно до четырёх HTTP-вызовов. В рабочем развёртывании ThingsBoard 1 140 бакетов обрабатывались **139 секунд**.

Узкое место — не арифметика, а количество сетевых обменов.

## Идея

Диапазон `[start, end)` разбивается на **полные календарные единицы** от месяца до минуты. Сначала снимаются полные месяцы; частичные края передаются на следующий, более мелкий уровень; остаток меньше минуты становится отдельным «хвостом». Затем каждый уровень один раз запрашивается агрегацией следующего, более мелкого уровня и сворачивается локально.

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

месяц   2026-01 … 2026-09          9 сегментов
день    10-01 … 10-20             20 сегментов
час     10-21 00:00 … 17:00       18 сегментов
минута  10-21 18:00 … 18:48       49 сегментов
хвост   10-21 18:49:00–18:49:59    1 сегмент
                                  ────────────
                                  97 сегментов
```

**97 сегментов вместо 423 049 минутных бакетов** (примерно в 4 360 раз меньше). Типичный запрос за 10 месяцев требует **5–7 запросов агрегации**, а не тысяч.

## Установка

```bash
# v0.0.4 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.4/hybrid_recursive_ladder-0.0.4-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

Дополнительные extras:

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

Ядро разбиения не имеет сторонних зависимостей (только `tzdata` для часовых поясов IANA).

## Демо за 30 секунд

```bash
hybrid-ladder demo
```

Генерирует синтетические 15-минутные данные, разбирает 120 дней, материализует первые 90 дней в память, выполняет смешанный запрос «сначала локально» и проверяет совпадение итогов. Без базы данных, сети и настроек.

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## Библиотека

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 08:00
```

С локальным хранилищем:

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

## Пять способов использования

| Форма | Точка входа | Для чего |
|---|---|---|
| Библиотека Python | `from hybrid_ladder import ...` | встраивание в сервис или конвейер |
| CLI | `hybrid-ladder ...` | разовые проверки, скрипты, cron |
| HTTP API | `hybrid-ladder serve` | интеграция на любом языке, асинхронные задачи |
| MCP-сервер | `hybrid-ladder mcp` | ИИ-агенты и MCP-клиенты |
| Навык агента | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | установка как skill |

```bash
hybrid-ladder serve --port 8000     # OpenAPI: http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # MCP-сервер через stdio
```

## Правила (обязательные)

1. **Полуинтервал** `[start, end)`. Если конец совпадает с границей, эта единица в результат не входит.
2. **Только полные единицы**. Месяц/день/час/минута выводятся на своём уровне, только если полностью лежат внутри диапазона.
3. **Края рекурсивны**. Частичные левый и правый края уходят на следующий уровень; остаток меньше минуты становится отдельным хвостом.
4. **Локальный календарь**. Границы считаются в заданном часовом поясе IANA (по умолчанию `Asia/Shanghai`).
5. **Инвариант покрытия**. Сегменты упорядочены, непрерывны, не перекрываются, а их объединение точно равно `[start, end)`.

## Семантика значений

| Значение | Смысл | Отображение |
|---|---|---|
| `null` | нет измерений | `—` |
| `0.0` | измерения есть, сумма равна нулю | `0` |
| число | сумма измерений | число |

Каждый сегмент содержит `cnt` (наблюдённые точки/бакеты), `expected` (ожидаемые бакеты, только для сегментов источника) и `source` (`local`, `tb`, `mixed`, `empty`, `uncovered`). Низкий `cnt` относительно `expected` означает разреженные данные; сумма корректна для существующих точек, но данные не восполняются.

## Адаптеры

Движок зависит только от двух небольших структурных интерфейсов:

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

В комплекте: `MemorySource` / `MemoryStore`, `ThingsBoardSource`, `PostgresStore`. Для InfluxDB, Prometheus или ClickHouse достаточно реализовать эти методы.

## Сначала локальные данные, проверка и восстановление

* Покрытие фиксируется только до `now - 5 минут`; текущий «хвост» никогда не считается надёжными локальными данными.
* Запрошенный диапазон фиксируется даже при нуле точек («мы спросили, данных нет»), чтобы не запрашивать его снова.
* Перед перезаписью диапазона его покрытие удаляется: сбой на полпути не оставит покрытие, указывающее на неполные данные.
* `verify` сравнивает источник (авторитет) с локальным хранилищем по сегментам и только для расходящихся сегментов спускается до точек (`added`/`removed`/`changed`).
* `repair` удаляет локальный диапазон и заново загружает его из источника; удалённые в источнике точки исчезают локально.

## Ограничения

* В v0.0.4 реализован только `sum`. Для `avg` нужно взвешивание; для `meter_delta` — первое значение каждого сегмента.
* При пропусках в данных итог будет меньше физического. `cnt/expected` показывают разреженность, но данные не восполняются.
* ThingsBoard принимает около 700 бакетов и отклоняет 800; по умолчанию используется 500.
* Фоновые задачи живут в памяти процесса и теряются при перезапуске (результаты можно пересчитать).
* Из-за фиксированного размера бакетов свёртка день/час рассчитана на зоны с постоянным смещением, такие как `Asia/Shanghai`.

## Производительность (измерено)

| Сценарий | Сегменты | Запросы | Время |
|---|---:|---:|---:|
| 2 дня, минуты | 69 | ~4 | 0,64 с |
| 1 год, дни | 42 | ~4 | 1,18 с холодный / 0,20 с горячий |
| 10 месяцев, смешанные уровни | 97 | ~5–7 | меньше секунды |
| Локальное чтение | 42–90 | 0 | 9–19 мс |

Воспроизвести число сегментов и запросов без сети:

```bash
python examples/benchmark.py
```

## Документация

* [Спецификация алгоритма](docs/algorithm.md)
* [Архитектура](docs/architecture.md)
* [Справочник API](docs/api.md)
* [Бенчмарки](docs/benchmarks.md)
* [Смежные работы и позиционирование](docs/related-work.md)

## Лицензия

[MIT](LICENSE) © 2026 MagicSquarekey
