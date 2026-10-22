# -*- coding: utf-8 -*-
"""CLI tests."""

from __future__ import annotations

import json

import pytest

from hybrid_ladder import __version__
from hybrid_ladder.cli import main


def test_decompose_json(capsys):
    assert main([
        "decompose",
        "--start", "2026-01-01",
        "--end", "2026-10-21T18:49:59",
        "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 97
    assert payload["segments"][0]["label"] == "2026-01"


def test_decompose_table(capsys):
    assert main([
        "decompose",
        "--start", "2026-01-01",
        "--end", "2026-10-21T18:49:59",
    ]) == 0
    output = capsys.readouterr().out
    assert "97 segments" in output
    assert "2026-10-21 18:49" in output


def test_decompose_bad_range_returns_2(capsys):
    assert main([
        "decompose",
        "--start", "2026-02-01",
        "--end", "2026-01-01",
    ]) == 2
    assert "error:" in capsys.readouterr().err


def test_demo(capsys):
    assert main(["demo"]) == 0
    output = capsys.readouterr().out
    assert "totals match: YES" in output
    assert "verify (materialized 90 days): diff_series=0 diff_segments=0" in output


def test_sum_memory(capsys):
    assert main([
        "sum",
        "--series", "demo-chiller-1:energy",
        "--start", "2026-01-01",
        "--end", "2026-02-01",
    ]) == 0
    output = capsys.readouterr().out
    assert "grand total:" in output
    assert "source: tb" in output


def test_sum_json(capsys):
    assert main([
        "sum",
        "--series", "demo-chiller-1:energy",
        "--start", "2026-01-01",
        "--end", "2026-02-01",
        "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["grand_total"] is not None
    assert payload["rows"][0]["segments_count"] == 1


def test_sum_mixed_without_dsn_returns_2(capsys):
    assert main([
        "sum",
        "--series", "demo-chiller-1:energy",
        "--start", "2026-01-01",
        "--end", "2026-02-01",
        "--mode", "mixed",
    ]) == 2
    assert "needs --dsn" in capsys.readouterr().err


def test_invalid_series_is_argparse_error():
    with pytest.raises(SystemExit) as exc:
        main([
            "sum",
            "--series", "bad",
            "--start", "2026-01-01",
            "--end", "2026-02-01",
        ])
    assert exc.value.code == 2


def test_invalid_time_is_argparse_error():
    with pytest.raises(SystemExit) as exc:
        main(["decompose", "--start", "not-a-time", "--end", "2026-02-01"])
    assert exc.value.code == 2


def test_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_custom_series_gets_synthetic_demo_data(capsys):
    assert main([
        "sum",
        "--series", "my-device:my-key",
        "--start", "2026-01-01",
        "--end", "2026-02-01",
        "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"][0]["device_id"] == "my-device"
    assert payload["grand_total"] is not None
