# ハイブリッド再帰ラダーアルゴリズム（Hybrid Recursive Ladder Algorithm）

**数千回のバケット単位クエリを、わずか数回のデータソースリクエストに。**

**言語 / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.4-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23557574.svg)](https://doi.org/10.5281/zenodo.23557574)

<p align="center">
  <img src="docs/assets/hero.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>同じ出力。まったく違うリクエスト数。</em></p>

## 課題

多くの時系列 API はリクエスト数・バケット数・往復回数で課金されます。「統計バケットごとに 1 回問い合わせる」実装では、2 日間の分単位クエリが 2,880 バケット、各バケット最大 4 回の HTTP 呼び出しになります。本番の ThingsBoard 環境では 1,140 バケットに **139 秒** かかりました。

ボトルネックは計算ではなく、ネットワーク往復です。

## アイデア

`[start, end)` を **月 → 日 → 時 → 分** の完全な暦単位に再帰的に分割します。完全な月を先に剥がし、左右の端数は次の細かい層へ送り、最細層の 1 分未満の端数は独立した「テール」にします。取得時は各層を「次の細かい層の集約」で 1 回だけ取得し、ローカルで畳み込みます。

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

月    2026-01 … 2026-09          9 セグメント
日    10-01 … 10-20             20 セグメント
時    10-21 00:00 … 17:00       18 セグメント
分    10-21 18:00 … 18:48       49 セグメント
端数  10-21 18:49:00–18:49:59    1 セグメント
                                ─────────────
                                97 セグメント
```

**423,049 個の分バケットが 97 セグメントに**（約 4,360 倍の圧縮）。10 か月のクエリでも集約リクエストは通常 **5〜7 回** です。

## インストール

```bash
# v0.0.4 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.4/hybrid_recursive_ladder-0.0.4-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

オプション:

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

コアの分解処理はサードパーティ依存がありません（IANA タイムゾーン用の `tzdata` のみ）。

## 30 秒デモ

```bash
hybrid-ladder demo
```

合成 15 分データを生成し、120 日間を分解し、最初の 90 日をメモリにマテリアライズし、ローカル優先の混合クエリを実行し、合計が一致することを検証します。データベースもネットワークも設定も不要です。

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## ライブラリ

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 08:00
```

ローカルストアを使う場合:

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

## 5 つの利用形態

| 形態 | エントリポイント | 用途 |
|---|---|---|
| Python ライブラリ | `from hybrid_ladder import ...` | サービスへの組み込み |
| CLI | `hybrid-ladder ...` | 調査・スクリプト・cron |
| HTTP API | `hybrid-ladder serve` | 言語非依存の連携・非同期タスク |
| MCP サーバー | `hybrid-ladder mcp` | AI エージェント / MCP クライアント |
| エージェントスキル | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | スキルとしての導入 |

```bash
hybrid-ladder serve --port 8000     # OpenAPI: http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # stdio の MCP サーバー
```

## ルール（不可変）

1. **左閉右開** `[start, end)`。終点がちょうど境界の場合、その単位は存在しません。
2. **完全な単位のみ**。月/日/時/分は区間内に完全に収まる場合だけその層で出力します。
3. **端数は下の層へ**。左端・右端の端数は次の細かい層で分解し、1 分未満は独立したテールにします。
4. **ローカル暦**。設定した IANA タイムゾーン（既定 `Asia/Shanghai`）で境界を計算します。
5. **タイル不変条件**。セグメントは順序どおり連続し、重複せず、和集合が `[start, end)` に一致します。

## 値の意味

| 値 | 意味 | 表示 |
|---|---|---|
| `null` | サンプルなし | `—` |
| `0.0` | サンプルはあるが合計 0 | `0` |
| 数値 | サンプルの合計 | 数値 |

各セグメントは `cnt`（実測ポイント/バケット数）、`expected`（本来のバケット数、データソースのみ）、`source`（`local` / `tb` / `mixed` / `empty` / `uncovered`）を持ちます。`cnt` が `expected` より著しく少ない場合はデータが疎です。合計は実在するポイントのみで計算され、補間はしません。

## アダプター

エンジンは 2 つの小さなインターフェースに依存します:

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

組み込み: `MemorySource` / `MemoryStore`、`ThingsBoardSource`、`PostgresStore`。InfluxDB・Prometheus・ClickHouse などはこのメソッドを実装するだけで接続できます。

## ローカル優先・検証・修復

* カバレッジは `now - 5 分` までしか記録しません。進行中の末尾は決して信頼できるローカルデータになりません。
* データソースに問い合わせた区間は、0 ポイントでも「確認済み」として記録し、次回の再取得を防ぎます。
* 区間を書き換える前にカバレッジを消去するため、途中で失敗しても不完全なローカルデータを信頼しません。
* `verify` はデータソース（権威）とローカルをセグメント単位で比較し、差異セグメントだけをポイント単位（追加/削除/変更）で掘り下げます。
* `repair` はローカル区間を削除し、データソースから再取得します。データソースで削除されたポイントはローカルからも消えます。

## 制限

* v0.0.4 は `sum` のみ。`avg` は加重、`meter_delta` は各セグメントの先頭値が必要で未実装です。
* データ欠損があると合計は物理的な総量より小さくなります。`cnt/expected` で疎であることを示すだけで、補間はしません。
* ThingsBoard の区間集約は約 700 バケットまで（800 は拒否）。既定は 500 です。
* バックグラウンドタスクはプロセスメモリ上にあり、再起動で失われます（結果は再計算可能）。
* 固定長バケットのため、日/時の畳み込みは `Asia/Shanghai` のような固定オフセット時間帯に最適です。

## 性能（実測）

| シナリオ | セグメント | リクエスト | 時間 |
|---|---:|---:|---:|
| 2 日・分単位 | 69 | 約 4 | 0.64 秒 |
| 1 年・日単位 | 42 | 約 4 | 冷 1.18 秒 / 温 0.20 秒 |
| 10 か月・混合 | 97 | 約 5–7 | サブ秒 |
| ローカル読み取り | 42–90 | 0 | 9–19 ms |

ネットワークなしでセグメント数・リクエスト数を再現:

```bash
python examples/benchmark.py
```

## ドキュメント

* [アルゴリズム仕様](docs/algorithm.md)
* [アーキテクチャ](docs/architecture.md)
* [API リファレンス](docs/api.md)
* [ベンチマーク](docs/benchmarks.md)
* [関連研究と位置づけ](docs/related-work.md)

## ライセンス

[MIT](LICENSE) © 2026 MagicSquarekey
