# Changelog

**语言 / Languages:** [English](CHANGELOG.md) · [简体中文](CHANGELOG.zh-CN.md)

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) from 0.0.1 onward.

## [0.0.6] — 2026-10-27

Documentation and site release. No algorithm, API, wire-format or storage
changes.

### Added

* Chinese versions for every document in the repository. All 14 prose documents
  now have a `.zh-CN.md` mirror — including the API reference, architecture,
  benchmarks, changelog, contributing guide and the agent skill — and the
  prior-art matrix has a Chinese CSV.
* `docs/README.md` / `docs/README.zh-CN.md`: a documentation index for every
  document, project-level file and diagram in both languages.
* `tools/check_docs_i18n.py`: fails CI when a document lacks a Chinese mirror,
  a diagram lacks `zh-CN` SVG/PNG assets, or a new document is not registered.
* An 11-language switcher on the documentation site, with `?lang=` deep links,
  a saved preference, translated metadata and right-to-left layout for Arabic.

### Changed

* Every document carries an English / 简体中文 switch at the top.
* Chinese documents use the Chinese diagrams; other languages keep the English
  or their localized hero image.
* On the site, Chinese mode links to the Chinese editions of the algorithm,
  prior-art, article and disclosure pages.
* Install snippets, badges, API examples and metadata now reference `0.0.6`.

### Fixed

* The benchmark table on the landing page no longer collapses: the badge rule
  is scoped to cards and wide tables scroll horizontally.
* Numeric ranges and arrows keep left-to-right order in the Arabic RTL layout.

## [0.0.5] — 2026-10-26

### Added

* MCP tool annotations on all four tools: a human-readable `title` plus
  `readOnlyHint`, `destructiveHint`, `idempotentHint` and `openWorldHint`.
  Clients can now tell that `ladder_meta` and `ladder_decompose` are local and
  side-effect free, that `ladder_sum` can write to the local store through
  `materialize=True`, and that `ladder_verify` reaches the source.
* Per-language README diagrams. `docs/assets/hero.<lang>.png` ships for every
  translated README, and `decomposition`/`architecture` are also localized for
  Chinese. `tools/localize_assets.py` regenerates them from the English SVGs.

### Fixed

* `tests/test_mcp.py` now accepts the `(content, structured)` return value of
  `call_tool` in current MCP SDK releases; the previous assertions failed on
  `mcp` 1.27 and later.

## [0.0.4] — 2026-10-22

Documentation release. No code or algorithm changes. Reworks the READMEs and
adds diagrams.

### Added

* Zenodo archive and DOI: [10.5281/zenodo.23557574](https://doi.org/10.5281/zenodo.23557574).

### Changed

* Reworked `README.md` and `README.zh-CN.md` into a single narrative with
  diagrams for the before/after comparison, calendar decomposition and
  local-first read path.
* Added the hero diagram and DOI/website badges to the other language READMEs.
* Bumped the package version to `0.0.4`.

## [0.0.3] — 2026-10-22

Archival release. No code or algorithm changes. This release triggers Zenodo's
GitHub integration so the public disclosure receives a DOI.

### Added

* Zenodo archive and DOI: [10.5281/zenodo.23556606](https://doi.org/10.5281/zenodo.23556606).

### Changed

* Bumped the package version to `0.0.3` and updated citation, install and site
  metadata for the archival release.

## [0.0.2] — 2026-10-22

Documentation and public-disclosure release. No algorithm semantics changed.

### Added

* `docs/defensive-publication.md`: a public disclosure of the method and its
  formal properties as prior art.
* `CITATION.cff` and `.zenodo.json`: citation and archive metadata.
* `docs/articles/why-per-bucket-queries-are-slow.md` and its Chinese mirror: a
  technical article with the production benchmark and prior-art framing.
* `docs/index.html`: a static landing page for GitHub Pages.
* `docs/publishing.md`: release, Zenodo, PyPI and distribution checklist.
* `docs/related-work.md` and `docs/related-work.zh-CN.md`: prior-art
  comparison, historical algorithms and a defensible novelty statement.
* `docs/prior-art-search.zh-CN.md` and `docs/prior-art-matrix.csv`: a
  repeatable prior-art/patent search plan and recording template.
* Formal refinement-locality, segment-count and request-count propositions in
  the algorithm specs.

### Changed

* Repositioned the project as a query-planning method for bucket-limited
  time-series APIs (README, algorithm spec, package description).
* Bumped the package version to `0.0.2` for the public-disclosure release.

## [0.0.1] — 2026-10-22

First standalone open-source release, extracted from AutoTestHub.

### Added

* Pure decomposition core (`month → day → hour → minute`) with configurable
  finest level, IANA timezone support and a strict tiling invariant.
* `LadderEngine` with source-only, local-only and local-first mixed reads.
* Local materialization with coverage tracking, a 5-minute grace period and
  rewrite-safe coverage invalidation.
* Segment-level verification with point-level drilling (`added`, `removed`,
  `changed`) and repair from the authoritative source.
* `TimeSeriesSource` and `PointStore` protocols; adapters for ThingsBoard,
  PostgreSQL, and in-memory use.
* PostgreSQL schema with monthly partitions, idempotent upserts, batched range
  sums and coverage tables (`hl_readings`, `hl_coverage`).
* ThingsBoard adapter handling the 500-bucket limit, mid-bucket timestamps,
  inclusive `endTs`, token refresh and error translation.
* `hybrid-ladder` CLI: `decompose`, `demo`, `sum`, `verify`, `repair`,
  `materialize`, `serve`, `mcp`, `version`.
* FastAPI app with async tasks, progress, cancellation, synchronous variants
  and the `{"code":0,"data":...}` envelope.
* MCP server with `ladder_meta`, `ladder_decompose`, `ladder_sum` and
  `ladder_verify` (supports MCP 1.x and 2.x).
* Agent skill package under `skills/hybrid-recursive-ladder/`.
* Deterministic demo data and an end-to-end `hybrid-ladder demo`.
* 90+ tests covering decomposition, folding, mixed reads, materialization,
  verification, repair, tasks, API, CLI, MCP, ThingsBoard and PostgreSQL.

### Fixed (relative to the original AutoTestHub implementation)

* **Multi-level fetch grouping.** Fetch runs are grouped by fetch level +
  contiguity instead of adjacency only. The original fetched a whole
  multi-level range at the coarsest level, which assigned a full day's value to
  the first hour and lost the remaining hours/minutes.
  Regression: `tests/test_engine.py::test_multilevel_query_is_exact`.
* **Raw chunk boundary.** Bisection now uses `[a, mid)` and `[mid, b)` under the
  exclusive-end contract. The original used `mid + 1`, dropping a point that
  landed exactly on the split boundary.
  Regression: `tests/test_engine.py::test_raw_split_keeps_boundary_point`.

### Changed

* PostgreSQL tables are namespaced (`namespace`, `entity`, `name`) and use a
  configurable `table_prefix` instead of AutoTestHub's
  `connection_id/device_id/device`.
* `TaskRegistry` is reusable (multiple instances, TTL, max tasks) instead of a
  module-level singleton.
* The MCP tool layer and HTTP layer share one `runtime.engine_from_env()`.

### Known limitations

* Only the `sum` rule is implemented. `avg` and `meter_delta` need additional
  aggregation semantics.
* In-process task results are lost on restart (data is not).
* The original AutoTestHub `device_id` migration is not automatic.
