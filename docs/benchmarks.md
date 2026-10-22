# Benchmarks

These numbers come from a production AutoTestHub deployment (October 2026),
aggregating a single ThingsBoard series over a VPN. They are indicative, not a
guarantee: latency depends on network distance, ThingsBoard load, data density
and the number of series.

## The problem being measured

The original implementation issued **one query per statistical bucket**:

* a two-day minute-level range = 1,140 buckets;
* each bucket needed up to four HTTP requests (aggregation + boundary points);
* measured wall time: **139 seconds**.

The bottleneck was network round trips, not arithmetic.

## Results

| Scenario | Segments | Requests | Time | Correctness check |
|---|---:|---:|---:|---|
| 2 days, minute level | 69 | ~4 | 0.64 s | total 2,217,024.0 = sum of 2,566 raw points |
| 1 year, day level | 42 | ~4 | 1.18 s cold / 0.20 s warm | total 36,012,018.25 |
| 10 months, mixed levels | 97 | ~5–7 | sub-second | 423,049 minute buckets avoided |
| Local read, 42–90 segments | 42–90 | 0 | 9–19 ms | one SQL statement |
| Mixed read (3 local + 1 source segment) | 4 | 1 | 0.31 s | equals source-only total |
| Verify + repair (1 tampered point) | — | — | — | 1 changed point found, 360 points rewritten, 0 diffs after |

The 10-month example compresses **423,049 per-minute buckets into 97 segments**
(~4,360× fewer units).

## Request-count model

For a range with `M` months, `D` days, `H` hours and `N` minutes:

```
aggregation requests ≈
    ceil(D_total / max_intervals)      # months
  + ceil(H_total / max_intervals)      # days
  + ceil(N_total / max_intervals)      # hours + minutes (shared fetch)
  + 1                                  # sub-minute tail, if present
```

`max_intervals` is 500 by default. ThingsBoard accepted 700 buckets and
rejected 800 in testing; the documented 1000 is not reliable.

Examples with `max_intervals=500`:

| Range | Buckets at the finest fetch level | Requests |
|---|---:|---:|
| 2 days, minute | 2,880 minute buckets | 6 (plus one tail) |
| 1 year, day | 365 day buckets | 1 |
| 10 months, mixed | ~294 day + ~480 hour + ~1,130 minute | ~6 |

The implementation may merge adjacent runs that share a fetch level (hours and
minutes), which is why the observed count is often lower than the sum of the
three terms.

## Local-first reads

After materializing a range, repeated queries read PostgreSQL:

* one batched SQL statement per series for all covered sub-ranges;
* 9–19 ms for 42–90 segments in the production database;
* only the uncovered sub-ranges hit ThingsBoard;
* a partially covered segment fetches only the missing slice.

A mixed read of three local segments plus one source segment took 0.31 s and
produced exactly the same total as a source-only query.

## Verification and repair

* Tampering with one local point (+999) produced one differing segment and one
  changed point at the expected timestamp.
* Repair rewrote 360 points for the range; a second verification reported zero
  differences.
* Point-level drilling is capped at 50 segments per report by default, so a
  large divergence cannot accidentally trigger a full re-download.

## Reproducing without a server

`examples/benchmark.py` wraps the in-memory source in a request counter and
runs the same decompositions. It measures **segment and request counts**, not
network latency, and is deterministic:

```bash
python examples/benchmark.py
```

Expected shape (the exact segment counts depend on the chosen start/end; these
ranges are intentionally not month-aligned):

```
range                        segments  agg_requests raw_requests
-----------------------------------------------------------------
2 days, minute                    100             3            0
10 months, mixed levels            97             3            1
1 year, day level                  47             3            0
```

The production 2-day query had 69 segments because its start/end differed; the
important stable metric is the request count, which stays in the single digits
regardless of range length.

## Caveats

* The production numbers include VPN latency; a co-located deployment will be
  faster, a high-latency link slower.
* Data density affects raw-point requests and materialization time, not the
  number of aggregation requests.
* ThingsBoard version and configuration can change the bucket limit; the
  adapter's `max_intervals` is configurable.
* The local read time depends on PostgreSQL hardware, partitioning and index
  cache. The schema uses the primary key `(namespace, entity, key, ts)`, so
  range scans are index-only for sums.
