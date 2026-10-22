# -*- coding: utf-8 -*-
"""Command-line interface.

Examples::

    hybrid-ladder demo
    hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
    hybrid-ladder sum --series demo-chiller-1:energy --start 2026-01-01 --end 2026-02-01
    hybrid-ladder serve --port 8000
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import __version__
from .demo import DEMO_SERIES, DEMO_STEP_MS, build_demo_source, demo_range
from .engine import LadderEngine
from .errors import ConfigurationError, LadderError
from .models import LEVELS, LadderConfig, SeriesRef

__all__ = ["main"]


# ----------------------------------------------------------------------
# Parsing helpers
# ----------------------------------------------------------------------
def parse_time(value: str, timezone: str = "Asia/Shanghai") -> int:
    """Parse ISO-8601 or epoch milliseconds."""
    text = value.strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid time {value!r}; use ISO-8601 or epoch milliseconds"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone))
    return round(dt.timestamp() * 1000)


def parse_series(value: str) -> SeriesRef:
    """Parse ``entity:key`` or ``entity:key:name``."""
    parts = value.split(":", 2)
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise argparse.ArgumentTypeError(
            f"invalid series {value!r}; use entity:key or entity:key:name"
        )
    return SeriesRef(parts[0], parts[1], parts[2] if len(parts) > 2 else None)


def iso(ts_ms: int, timezone: str = "Asia/Shanghai") -> str:
    return datetime.fromtimestamp(ts_ms / 1000, ZoneInfo(timezone)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _print_table(headers: list[str], rows: list[list[Any]]) -> None:
    widths = [len(h) for h in headers]
    text_rows = [[str(cell) for cell in row] for row in rows]
    for row in text_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * width for width in widths))
    for row in text_rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


# ----------------------------------------------------------------------
# Engine construction
# ----------------------------------------------------------------------
def _ensure_memory_series(source, refs: list[SeriesRef]) -> None:
    known = {(ref.entity, ref.key) for ref in DEMO_SERIES}
    start, end = demo_range()
    for index, ref in enumerate(refs):
        if (ref.entity, ref.key) in known:
            continue
        points = []
        ts = start
        step_index = 0
        while ts < end:
            phase = 2 * math.pi * (step_index * DEMO_STEP_MS / 86_400_000) + index
            value = 3.0 + 1.2 * math.sin(phase) + 0.2 * ((step_index * 29) % 7)
            points.append((ts, round(value, 3)))
            ts += DEMO_STEP_MS
            step_index += 1
        source.add(ref.entity, ref.key, points)


def _build_engine(args: argparse.Namespace, refs: list[SeriesRef] | None = None) -> LadderEngine:
    config = LadderConfig(
        finest=getattr(args, "finest", "minute"),
        timezone=getattr(args, "timezone", "Asia/Shanghai"),
    )
    source_name = getattr(args, "source", "memory")
    if source_name == "memory":
        source = build_demo_source()
        if refs:
            _ensure_memory_series(source, refs)
    elif source_name == "thingsboard":
        from .sources.thingsboard import ThingsBoardSource

        if not getattr(args, "tb_url", None):
            raise ConfigurationError(
                "--tb-url (or HL_TB_URL) is required for --source thingsboard"
            )
        source = ThingsBoardSource(
            args.tb_url,
            token=getattr(args, "tb_token", None),
            username=getattr(args, "tb_username", None),
            password=getattr(args, "tb_password", None),
        )
    else:  # pragma: no cover - argparse restricts choices
        raise SystemExit(f"unknown source: {source_name}")

    store = None
    dsn = getattr(args, "dsn", None)
    if dsn:
        from .stores.postgres import PostgresStore

        store = PostgresStore(
            dsn,
            namespace=getattr(args, "namespace", "default"),
            table_prefix=getattr(args, "table_prefix", "hl_"),
            timezone=config.timezone,
        )
    return LadderEngine(source, store, config)


def _common_series_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--series",
        action="append",
        type=parse_series,
        default=[],
        metavar="ENTITY:KEY[:NAME]",
        help="repeatable series reference",
    )
    parser.add_argument("--start", required=True, help="ISO-8601 or epoch milliseconds")
    parser.add_argument("--end", required=True, help="ISO-8601 or epoch milliseconds (exclusive)")
    parser.add_argument("--finest", default="minute", choices=LEVELS)
    parser.add_argument("--timezone", default=os.getenv("HL_TIMEZONE", "Asia/Shanghai"))
    parser.add_argument("--source", choices=["memory", "thingsboard"], default=os.getenv("HL_SOURCE", "memory"))
    parser.add_argument("--tb-url", default=os.getenv("HL_TB_URL"))
    parser.add_argument("--tb-token", default=os.getenv("HL_TB_TOKEN"))
    parser.add_argument("--tb-username", default=os.getenv("HL_TB_USERNAME"))
    parser.add_argument("--tb-password", default=os.getenv("HL_TB_PASSWORD"))
    parser.add_argument("--dsn", default=os.getenv("HL_PG_DSN"), help="PostgreSQL DSN (enables local store)")
    parser.add_argument("--namespace", default=os.getenv("HL_NAMESPACE", "default"))
    parser.add_argument("--table-prefix", default=os.getenv("HL_TABLE_PREFIX", "hl_"))
    parser.add_argument("--json", action="store_true", help="print raw JSON")


def _refs(args: argparse.Namespace) -> list[SeriesRef]:
    refs = list(args.series)
    if not refs and args.source == "memory":
        refs = list(DEMO_SERIES)
    if not refs:
        raise SystemExit("provide at least one --series")
    return refs


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------
def cmd_decompose(args: argparse.Namespace) -> int:
    start = parse_time(args.start, args.timezone)
    end = parse_time(args.end, args.timezone)
    from .core import decompose

    segments = decompose(start, end, args.finest, timezone=args.timezone)
    if args.json:
        print(json.dumps(
            {"segments": [s.as_dict() for s in segments], "count": len(segments)},
            ensure_ascii=False,
            indent=2,
        ))
        return 0
    rows = []
    for segment in segments:
        rows.append([
            segment.level,
            segment.label,
            iso(segment.start, args.timezone),
            iso(segment.end, args.timezone),
            f"{segment.duration_ms / 60_000:.0f}m",
        ])
    _print_table(["LEVEL", "LABEL", "START", "END", "DURATION"], rows)
    by_level: dict[str, int] = {}
    for segment in segments:
        by_level[segment.level] = by_level.get(segment.level, 0) + 1
    print()
    print(f"{len(segments)} segments: " + ", ".join(f"{k}={v}" for k, v in by_level.items()))
    return 0


def cmd_sum(args: argparse.Namespace) -> int:
    refs = _refs(args)
    start = parse_time(args.start, args.timezone)
    end = parse_time(args.end, args.timezone)
    engine = _build_engine(args, refs)
    mode = args.mode
    if mode in ("mixed", "local") and engine.store is None:
        raise ConfigurationError("--mode mixed/local needs --dsn (or HL_PG_DSN)")
    if mode == "tb":
        result = engine.sum(refs, start, end, finest=args.finest)
    elif mode == "local":
        result = engine.sum_local(refs, start, end, finest=args.finest)
    else:
        result = engine.sum_mixed(refs, start, end, finest=args.finest)
    if args.materialize and engine.store is not None:
        items = (
            [(ref, [(start, end)]) for ref in refs]
            if mode == "tb"
            else [(row.ref, row.tb_ranges) for row in result.rows if row.tb_ranges]
        )
        if items:
            result.materialized = engine.materialize_ranges(items)
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0
    rows = [
        [row.ref.display_name, row.ref.key, _fmt(row.total), row.segments_count,
         row.empty_count, len(row.tb_ranges), row.error or ""]
        for row in result.rows
    ]
    _print_table(
        ["DEVICE", "KEY", "TOTAL", "SEGMENTS", "EMPTY", "TB_RANGES", "ERROR"], rows
    )
    print()
    print(f"grand total: {_fmt(result.grand_total)}  source: {result.source}")
    if result.source_counts:
        print("segments by source: " + ", ".join(
            f"{k}={v}" for k, v in sorted(result.source_counts.items())
        ))
    if result.materialized:
        print(f"materialized: {result.materialized.get('written')} points")
    if result.materialize_error:
        print(f"materialize error: {result.materialize_error}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    refs = _refs(args)
    start = parse_time(args.start, args.timezone)
    end = parse_time(args.end, args.timezone)
    engine = _build_engine(args, refs)
    if engine.store is None:
        raise ConfigurationError("verify needs --dsn (or HL_PG_DSN)")
    report = engine.verify(refs, start, end, finest=args.finest, drill_limit=args.drill_limit)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(
        f"series={report['series']} segments={report['segments']} "
        f"diff_series={report['diff_series']} diff_segments={report['diff_segments']} "
        f"drilled={report['drilled']} skipped={report['drill_skipped']}"
    )
    for detail in report["details"]:
        print(f"\n{detail['device_name']} · {detail['key']}")
        for diff in detail["diffs"]:
            print(
                f"  {diff['label']:<20} tb={_fmt(diff['tb'])} local={_fmt(diff['local'])} "
                f"cnt={diff['local_cnt']}"
                + (
                    f" added={diff['added']} removed={diff['removed']} changed={diff['changed']}"
                    if "added" in diff
                    else " (drill skipped)"
                )
            )
    return 0


def cmd_repair(args: argparse.Namespace) -> int:
    refs = _refs(args)
    start = parse_time(args.start, args.timezone)
    end = parse_time(args.end, args.timezone)
    engine = _build_engine(args, refs)
    if engine.store is None:
        raise ConfigurationError("repair needs --dsn (or HL_PG_DSN)")
    result = engine.repair(refs, start, end)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    for row in result["series"]:
        print(f"{row['device_name']} · {row['key']}: deleted={row['deleted']} inserted={row['inserted']}")
    return 0


def cmd_materialize(args: argparse.Namespace) -> int:
    refs = _refs(args)
    start = parse_time(args.start, args.timezone)
    end = parse_time(args.end, args.timezone)
    engine = _build_engine(args, refs)
    if engine.store is None:
        raise ConfigurationError("materialize needs --dsn (or HL_PG_DSN)")
    result = engine.materialize(refs, start, end)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"materialized {result['written']} points over {result['ranges']} ranges")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    start, end = demo_range()
    source = build_demo_source()
    from .stores.memory import MemoryStore

    store = MemoryStore()
    engine = LadderEngine(source, store, LadderConfig(timezone=args.timezone))
    refs = list(DEMO_SERIES)

    segments = engine.decompose(start, end)
    by_level: dict[str, int] = {}
    for segment in segments:
        by_level[segment.level] = by_level.get(segment.level, 0) + 1
    print("Hybrid Recursive Ladder — end-to-end demo")
    print(f"range: {iso(start, args.timezone)} → {iso(end, args.timezone)}")
    print(f"decomposition: {len(segments)} segments (" +
          ", ".join(f"{k}={v}" for k, v in by_level.items()) + ")")
    print(f"raw points: {sum(len(source.points(r.entity, r.key)) for r in refs)} "
          f"(per-minute queries would be {((end - start) // 60_000):,} buckets per series)")

    pure = engine.sum(refs, start, end)
    print(f"\nsource-only sum: grand_total={_fmt(pure.grand_total)} "
          f"source={pure.source} segments={sum(r.segments_count for r in pure.rows)}")

    covered_end = start + 90 * 86_400_000  # first three full months
    materialized = engine.materialize(refs, start, covered_end)
    print(f"materialized first 90 days: {materialized['written']} points")

    mixed = engine.sum_mixed(refs, start, end)
    print(f"mixed sum:       grand_total={_fmt(mixed.grand_total)} "
          f"source={mixed.source} "
          f"counts={mixed.source_counts}")
    match = pure.grand_total == mixed.grand_total
    print(f"totals match: {'YES' if match else 'NO'}")

    report = engine.verify(refs, start, covered_end)
    print(f"verify (materialized 90 days): diff_series={report['diff_series']} "
          f"diff_segments={report['diff_segments']} drilled={report['drilled']}")
    print("\nTip: run 'hybrid-ladder serve --port 8000' for the HTTP API, "
          "or see docs/api.md for MCP and library usage.")
    return 0 if match and report["diff_segments"] == 0 else 1


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        raise SystemExit(
            "serve needs uvicorn: pip install -e \".[api]\" (source checkout)"
        ) from None
    try:
        from .api import create_app
    except ImportError as exc:
        raise SystemExit(
            "serve needs fastapi: pip install -e \".[api]\" (source checkout)"
        ) from exc

    engine = _build_engine(args)
    app = create_app(engine=engine)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def cmd_mcp(_: argparse.Namespace) -> int:
    try:
        from .mcp_server import run
    except ImportError as exc:
        raise SystemExit(
            "MCP server needs the mcp package: pip install -e \".[mcp]\" (source checkout)"
        ) from exc
    run()
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.3f}"


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hybrid-ladder",
        description="Hybrid Recursive Ladder Algorithm — fast long-range time-series aggregation.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_dec = sub.add_parser("decompose", help="show the ladder decomposition of a range")
    p_dec.add_argument("--start", required=True)
    p_dec.add_argument("--end", required=True)
    p_dec.add_argument("--finest", default="minute", choices=LEVELS)
    p_dec.add_argument("--timezone", default=os.getenv("HL_TIMEZONE", "Asia/Shanghai"))
    p_dec.add_argument("--json", action="store_true")
    p_dec.set_defaults(func=cmd_decompose)

    p_demo = sub.add_parser("demo", help="run an end-to-end demo with synthetic data")
    p_demo.add_argument("--timezone", default="Asia/Shanghai")
    p_demo.set_defaults(func=cmd_demo)

    p_sum = sub.add_parser("sum", help="sum one or more series")
    _common_series_args(p_sum)
    p_sum.add_argument("--mode", choices=["tb", "mixed", "local"], default="tb")
    p_sum.add_argument("--materialize", action="store_true",
                       help="write missing raw points to the local store after the query")
    p_sum.set_defaults(func=cmd_sum)

    p_verify = sub.add_parser("verify", help="compare the source with the local store")
    _common_series_args(p_verify)
    p_verify.add_argument("--drill-limit", type=int, default=50)
    p_verify.set_defaults(func=cmd_verify)

    p_repair = sub.add_parser("repair", help="replace the local range with source data")
    _common_series_args(p_repair)
    p_repair.set_defaults(func=cmd_repair)

    p_mat = sub.add_parser("materialize", help="pull raw points into the local store")
    _common_series_args(p_mat)
    p_mat.set_defaults(func=cmd_materialize)

    p_serve = sub.add_parser("serve", help="run the HTTP API")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--timezone", default=os.getenv("HL_TIMEZONE", "Asia/Shanghai"))
    p_serve.add_argument("--source", choices=["memory", "thingsboard"], default=os.getenv("HL_SOURCE", "memory"))
    p_serve.add_argument("--tb-url", default=os.getenv("HL_TB_URL"))
    p_serve.add_argument("--tb-token", default=os.getenv("HL_TB_TOKEN"))
    p_serve.add_argument("--tb-username", default=os.getenv("HL_TB_USERNAME"))
    p_serve.add_argument("--tb-password", default=os.getenv("HL_TB_PASSWORD"))
    p_serve.add_argument("--dsn", default=os.getenv("HL_PG_DSN"))
    p_serve.add_argument("--namespace", default=os.getenv("HL_NAMESPACE", "default"))
    p_serve.add_argument("--table-prefix", default=os.getenv("HL_TABLE_PREFIX", "hl_"))
    p_serve.set_defaults(func=cmd_serve)

    p_mcp = sub.add_parser("mcp", help="run the MCP server over stdio")
    p_mcp.set_defaults(func=cmd_mcp)

    p_version = sub.add_parser("version", help="print the version")
    p_version.set_defaults(func=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
        return 2  # pragma: no cover - parser.error raises SystemExit
    except (LadderError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
