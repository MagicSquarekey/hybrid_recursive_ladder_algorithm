# Contributing

Thanks for considering a contribution. This project values correctness and
clarity over feature count: the algorithm's guarantees are the product.

## Development setup

```bash
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check .
pytest
```

Optional PostgreSQL integration tests:

```bash
export HL_TEST_PG_DSN='postgresql://user:pass@127.0.0.1:5432/testdb'
pytest -m integration
```

The integration test uses a unique `namespace` and the `hl_test_` table prefix;
it cleans its rows after each test.

## What to run before opening a PR

```bash
ruff check .
pytest
python examples/benchmark.py       # segment/request counts should stay stable
```

If you change algorithm semantics, update `docs/algorithm.md`,
`docs/algorithm.zh-CN.md` and the relevant test in the same PR.

## Commit messages

Conventional Commits are preferred:

```
feat(engine): add max/min folding
fix(core): keep boundary point on raw bisection
docs(api): document sync endpoints
test(mixed): cover grace-period clamping
```

Keep a commit focused. A bug fix should include a regression test that fails
before the fix.

## Adding a source adapter

1. Implement `interval_agg` and `raw_series` from
   `hybrid_ladder.protocols.TimeSeriesSource`.
2. Return `{bucket_start_ms: value}` from `interval_agg`; normalize any
   mid-bucket timestamps your source uses.
3. Enforce `[start, end)` and ascending order in `raw_series`; return at most
   `limit` points.
4. Keep credentials out of logs and error messages.
5. Add tests with `httpx.MockTransport` (for HTTP sources) or a deterministic
   fixture. Cover: bucket normalization, chunking, auth, error translation and
   the exclusive end.

## Adding a store adapter

1. Implement the seven methods from `hybrid_ladder.protocols.PointStore`.
2. Return `(None, 0)` for an empty range and `(0.0, n)` for a zero-valued
   range. This distinction is a core guarantee.
3. Make `upsert_points` idempotent on `(entity, key, ts)`.
4. `clear_coverage` must remove overlapping coverage rows before a rewrite.
5. `series` may paginate internally; `max_points` is a page size, not a cap.
6. Add an opt-in integration test gated by an environment variable.

## Code style

* Python 3.10+, type hints on public functions.
* Line length 100, `ruff` with the configured rule set.
* The core (`core.py`) must remain free of I/O and third-party dependencies.
* Prefer explicit names over abbreviations; comments should explain
  constraints, not restate code.

## Documentation

* English is the primary README; keep `README.zh-CN.md` in sync when behavior
  changes.
* API changes require an update to `docs/api.md` and `CHANGELOG.md`.
* Add benchmarks only with methodology and caveats; never present a
  single-machine number as a guarantee.
* README diagrams are language-specific: `docs/assets/<name>.<lang>.png` is
  rendered from the English `docs/assets/<name>.svg` by
  `python tools/localize_assets.py`. After editing an SVG or a translation,
  re-run it; `--check` reports strings that have no translation yet.

## Release process

1. Update `CHANGELOG.md` and the version in `pyproject.toml`.
2. Run `ruff check .`, `pytest`, and `python -m build`.
3. Commit, tag (`vX.Y.Z`), and push the tag. The `release.yml` workflow builds
   the distributions and creates the GitHub release.
4. If PyPI publishing is enabled, use trusted publishing with the `pypi`
   environment.

## Reporting issues

Please include:

* the range and `finest` level,
* the source type and adapter version,
* the expected and actual totals/segment counts,
* whether the local store was involved (`source` / `source_counts`),
* a minimal reproduction when possible.

Never include credentials or production data in an issue.
