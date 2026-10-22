# 하이브리드 재귀 사다리 알고리즘 (Hybrid Recursive Ladder Algorithm)

**수천 번의 버킷별 쿼리를 단 몇 번의 데이터 소스 요청으로.**

**언어 / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.4-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23557574.svg)](https://doi.org/10.5281/zenodo.23557574)

<p align="center">
  <img src="docs/assets/hero.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>같은 출력, 전혀 다른 요청 수.</em></p>

## 문제

대부분의 시계열 API는 요청 수, 버킷 수 또는 왕복 횟수로 과금합니다. "통계 버킷마다 한 번씩 질의"하는 구현은 이틀치 분 단위 쿼리를 2,880개 버킷으로 만들고, 버킷마다 최대 4번의 HTTP 호출이 필요합니다. 실제 ThingsBoard 환경에서 1,140개 버킷에 **139초**가 걸렸습니다.

병목은 계산이 아니라 네트워크 왕복입니다.

## 아이디어

`[start, end)`를 **월 → 일 → 시 → 분**의 완전한 달력 단위로 재귀 분해합니다. 완전한 월을 먼저 벗겨내고, 양쪽 끝의 부분 구간은 다음 세밀한 계층으로 넘기며, 최세밀 계층의 1분 미만 잔여 구간은 별도의 "꼬리" 세그먼트가 됩니다. 조회할 때는 각 계층을 "한 단계 더 세밀한 집계"로 한 번에 가져와 로컬에서 합산합니다.

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

월    2026-01 … 2026-09          9개 세그먼트
일    10-01 … 10-20             20개 세그먼트
시    10-21 00:00 … 17:00       18개 세그먼트
분    10-21 18:00 … 18:48       49개 세그먼트
꼬리  10-21 18:49:00–18:49:59    1개 세그먼트
                                ─────────────
                                97개 세그먼트
```

**423,049개의 분 버킷이 97개 세그먼트로** 줄어듭니다(약 4,360배 압축). 10개월 쿼리도 보통 집계 요청 **5~7회**면 충분합니다.

## 설치

```bash
# v0.0.4 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.4/hybrid_recursive_ladder-0.0.4-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

선택 사항:

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

핵심 분해 로직은 서드파티 의존성이 없습니다(IANA 시간대용 `tzdata`만 필요).

## 30초 데모

```bash
hybrid-ladder demo
```

합성 15분 데이터를 생성하고, 120일 구간을 분해하고, 처음 90일을 메모리에 구체화한 뒤, 로컬 우선 혼합 쿼리를 실행하고, 합계가 일치하는지 검증합니다. 데이터베이스, 네트워크, 설정이 필요 없습니다.

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## 라이브러리

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 08:00
```

로컬 저장소 사용:

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

## 다섯 가지 사용 형태

| 형태 | 진입점 | 용도 |
|---|---|---|
| Python 라이브러리 | `from hybrid_ladder import ...` | 서비스/데이터 파이프라인 |
| CLI | `hybrid-ladder ...` | 조사, 스크립트, cron |
| HTTP API | `hybrid-ladder serve` | 언어 독립 연동, 비동기 작업 |
| MCP 서버 | `hybrid-ladder mcp` | AI 에이전트 / MCP 클라이언트 |
| 에이전트 스킬 | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | 스킬로 설치 |

```bash
hybrid-ladder serve --port 8000     # OpenAPI: http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # stdio MCP 서버
```

## 규칙(필수)

1. **왼쪽 닫힘, 오른쪽 열림** `[start, end)`. 끝이 정확히 경계이면 그 단위는 결과에 존재하지 않습니다.
2. **완전한 단위만**. 월/일/시/분은 구간 안에 완전히 들어갈 때만 해당 계층에서 출력합니다.
3. **끝 부분은 아래 계층으로**. 왼쪽/오른쪽 잔여 구간은 다음 세밀한 계층으로 넘기고, 1분 미만은 별도 꼬리로 만듭니다.
4. **로컬 달력**. 설정한 IANA 시간대(기본 `Asia/Shanghai`)로 경계를 계산합니다.
5. **타일링 불변식**. 세그먼트는 순서대로 연속되고, 겹치지 않으며, 합집합이 정확히 `[start, end)`입니다.

## 값 의미

| 값 | 의미 | 표시 |
|---|---|---|
| `null` | 샘플 없음 | `—` |
| `0.0` | 샘플은 있지만 합이 0 | `0` |
| 숫자 | 샘플 합계 | 숫자 |

각 세그먼트는 `cnt`(관측 포인트/버킷 수), `expected`(원래 있어야 할 버킷 수, 데이터 소스 전용), `source`(`local` / `tb` / `mixed` / `empty` / `uncovered`)를 가집니다. `cnt`가 `expected`보다 크게 낮으면 데이터가 희소하다는 뜻입니다. 합계는 실제 존재하는 포인트만 더하며, 보간하지 않습니다.

## 어댑터

엔진은 두 개의 작은 인터페이스에만 의존합니다:

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

내장: `MemorySource` / `MemoryStore`, `ThingsBoardSource`, `PostgresStore`. InfluxDB, Prometheus, ClickHouse 등은 이 메서드만 구현하면 연결됩니다.

## 로컬 우선, 검증, 복구

* 커버리지는 `now - 5분`까지만 기록합니다. 진행 중인 꼬리는 절대 신뢰할 수 있는 로컬 데이터가 아닙니다.
* 데이터 소스에 질의한 구간은 포인트가 0개여도 "확인함"으로 기록해 다음 번 재조회를 막습니다.
* 구간을 다시 쓰기 전에 커버리지를 지우므로, 중간에 실패해도 불완전한 로컬 데이터를 신뢰하지 않습니다.
* `verify`는 데이터 소스(권위)와 로컬을 세그먼트 단위로 비교하고, 차이가 있는 세그먼트만 포인트 단위(추가/삭제/변경)로 파고듭니다.
* `repair`는 로컬 구간을 삭제하고 데이터 소스에서 다시 가져옵니다. 데이터 소스에서 삭제된 포인트는 로컬에서도 사라집니다.

## 제한

* v0.0.4은 `sum`만 구현했습니다. `avg`는 가중치가 필요하고, `meter_delta`는 세그먼트별 첫 값이 필요합니다.
* 데이터 누락이 있으면 합계는 물리적 총량보다 작아집니다. `cnt/expected`로 희소성을 표시할 뿐 보간하지 않습니다.
* ThingsBoard 구간 집계는 약 700 버킷까지 허용(800 거부). 기본값은 500입니다.
* 백그라운드 작업은 프로세스 메모리에 있어 재시작 시 사라집니다(결과는 재계산 가능).
* 고정 길이 버킷 때문에 일/시 합산은 `Asia/Shanghai` 같은 고정 오프셋 시간대에 최적입니다.

## 성능(실측)

| 시나리오 | 세그먼트 | 요청 수 | 시간 |
|---|---:|---:|---:|
| 2일, 분 단위 | 69 | 약 4 | 0.64초 |
| 1년, 일 단위 | 42 | 약 4 | 콜드 1.18초 / 웜 0.20초 |
| 10개월, 혼합 | 97 | 약 5–7 | 1초 미만 |
| 로컬 읽기 | 42–90 | 0 | 9–19ms |

네트워크 없이 세그먼트/요청 수 재현:

```bash
python examples/benchmark.py
```

## 문서

* [알고리즘 명세](docs/algorithm.md)
* [아키텍처](docs/architecture.md)
* [API 참조](docs/api.md)
* [벤치마크](docs/benchmarks.md)
* [관련 연구 및 포지셔닝](docs/related-work.md)

## 라이선스

[MIT](LICENSE) © 2026 MagicSquarekey
