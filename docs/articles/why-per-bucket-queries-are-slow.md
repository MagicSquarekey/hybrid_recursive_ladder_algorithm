# 1,140 buckets, 139 seconds: why per-bucket time-series queries fail

A production ThingsBoard query over a VPN took **139 seconds** for 1,140
statistical buckets. The arithmetic was trivial. The network was not.

This is the story of a query planner that turned thousands of per-bucket
requests into a handful of requests by treating the calendar as the plan.

## The query

The client needed a minute-level aggregate for a long range. The naive
implementation asked the source once per statistical bucket, and each bucket
needed up to four HTTP calls: one aggregation plus boundary points.

At 1,140 buckets, that is up to 4,560 round trips. Over a VPN, with tens of
milliseconds per round trip, the wall time is dominated by the network. A full
two-day minute-level range would be 2,880 buckets; the production range happened
to be smaller.

The first instinct is to optimize the arithmetic. The arithmetic was never the
problem.

## Three obvious fixes, and why they are not enough

**1. Ask for one coarse interval.** If you request one bucket for the whole
range, you get one request, but you lose the per-minute or per-day rows the
dashboard needs. The output granularity is the product; you cannot throw it
away.

**2. Pre-aggregate.** Continuous aggregates, rollup tables, or a multi-resolution
store solve this well—if you control the database. A read-only telemetry API
usually does not let you create materialized views or change its retention
policy.

**3. Paginate.** Pagination reduces the page size, not the number of pages. It
also makes boundary handling worse: every page boundary is another place where a
point can be duplicated or dropped.

The useful question is different: **can the source return a coarser or finer
aggregation over a contiguous run, so that one request fills many output
units?** For most interval-aggregation APIs, the answer is yes.

## The calendar ladder

The output needs one value per complete calendar unit. The source does not need
one request per output unit. The ladder separates those two ideas.

### 1. Decompose into complete calendar units

Split `[start, end)` from month down to minute:

- emit only units that are fully contained in the range;
- push the partial left and right edges to the next finer level;
- at the finest level, emit the sub-unit remainder as a tail.

For `2026-01-01 00:00:00 → 2026-10-21 18:49:59`:

```
month   Jan … Sep                 9 segments
day     Oct 1 … Oct 20           20 segments
hour    Oct 21 00:00 … 17:00     18 segments
minute  Oct 21 18:00 … 18:48     49 segments
tail    Oct 21 18:49:00–18:49:59  1 segment
                                  ───────────
                                  97 segments
```

That is 97 output segments instead of 423,049 minute buckets. But the more
important number is the request count: **5–7 aggregation requests**, not
thousands.

### 2. Fetch each level at the next finer aggregation

The output level determines the output granularity, not the fetch granularity:

| Output level | Fetch level | Why |
|---|---|---|
| month | day | Most sources have no natural month interval; fold days. |
| day | hour | Avoids fixed-bucket day-boundary drift. |
| hour | minute | Folds exact minutes into hours. |
| minute | minute | Direct. |
| sub-minute tail | raw points | A bucket cannot represent a partial minute. |

For a month segment, ask the source for day buckets and sum the days. For a day
segment, ask for hour buckets. For an hour segment, ask for minute buckets. The
fold is local.

### 3. Group runs by fetch level and contiguity

This is the part that is easy to get wrong. Group adjacent segments only if they
also need the same fetch level.

- Hours and minutes both fetch at minute level, so they can share one run.
- Months fetch at day level and days fetch at hour level, so they cannot share a
  run.

Grouping only by adjacency causes a multi-level range to be fetched at the
coarsest level, assigning a whole day's value to the first hour and losing the
rest. In the original implementation this was a real correctness bug, not just a
performance issue.

### 4. Fold locally

Sum the returned buckets whose start falls inside each output segment. The
source does the expensive aggregation over a long run; the client does a cheap
fold over a small number of buckets.

## The request bound

Let `K` be the maximum number of buckets the source accepts per request. For a
fetch run of duration `T` at bucket size `Δ`, the adapter splits the run into
windows of `K * Δ`:

```
requests(run) = ceil(T / (K * Δ))
```

The total is the sum over runs. In the common contiguous case there are at most
three aggregation runs (day, hour, minute), so the sum has at most three terms.

For the 10-month example with `K = 500`:

```
months          -> day fetch:    273 buckets -> 1 request
days            -> hour fetch:   480 buckets -> 1 request
hours + minutes -> minute fetch: 1,129 buckets -> 3 requests
R_agg ~= 5
```

The structural reason is that fine-grained work is confined to the two partial
units at the edges. For the default hierarchy:

```
N_day    <= 2 * 31 = 62
N_hour   <= 4 * 24 = 96
N_minute <= 8 * 60 = 480
tail     <= 1
N <= N_month + 639
```

Recursion depth is at most the number of levels (4). A ten-year range does not
explode into minutes; it produces roughly one segment per month plus a bounded
amount of edge work. The request count grows as
`O(N_month / K + 1)`, not as the number of minute buckets.

## Local-first reads

The same decomposition is useful when you have a local point store. Each output
segment is split against the merged coverage ranges:

1. Sum covered sub-ranges with one batched local query.
2. Fetch fully uncovered segments with grouped aggregation.
3. For partially covered segments, fetch only the missing slice.
4. Segment value = local part + source part.

In the production deployment, local reads of 42–90 segments took 9–19 ms, and a
mixed read of three local segments plus one source segment took 0.31 s with the
same total as a source-only query. Coverage is only recorded up to
`now - grace`, and it is invalidated before a rewrite, so a failed pull is
re-fetched rather than trusted.

## What this is not

This is a query-planning composition, not a new general theory of aggregation.
The ingredients have prior art:

- **RRDtool / Whisper**: multi-resolution archives and consolidation.
- **BTrDB**: time-partitioned tree with per-node summaries.
- **TimescaleDB hierarchical continuous aggregates**: minute → hour → day
  roll-up.
- **Apache Druid period granularity**: calendar-aligned buckets with time zones.
- **Prometheus / Grafana**: point caps and single-step downsampling.
- **Segment trees**: canonical aligned interval decomposition.
- **Hierarchical timing wheels**: level + remainder cascade for timers.

The specific combination is the contribution: calendar hierarchy as the query
plan, next-finer fetch, fetch-level grouping, coverage-aware gap filling, and a
request plan under a hard bucket cap. The method is published as a
[public disclosure](../defensive-publication.md) and the implementation is MIT
licensed.

## When to use it

Use it when:

- you can read an interval-aggregation endpoint but cannot write to or
  reconfigure the source;
- the source has a hard per-request bucket or point limit;
- the output is calendar-shaped (month, day, hour, minute);
- you can tolerate local folding and the documented DST caveat;
- you want local caching without changing the source.

Do not use it when:

- you control the database: use continuous aggregates or a multi-resolution
  store instead;
- you need exact `avg`, percentiles or meter deltas: the current release only
  implements `sum`;
- you need exact sub-minute behavior across DST transitions: use raw points or a
  finer fetch level;
- the source has no interval-aggregation endpoint at all.

## Reproduce it

```bash
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.2/hybrid_recursive_ladder-0.0.2-py3-none-any.whl

hybrid-ladder demo
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
python examples/benchmark.py
```

The benchmark prints segment and request counts without a server.

## The takeaway

If your time-series API charges per request or caps buckets per request, the
number of round trips is the design variable. You do not always need a new
database. Sometimes you need to stop asking one question per output row and
start planning the range as a calendar.

---

*Repository: <https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm> · Algorithm specification:
[`docs/algorithm.md`](../algorithm.md) · Prior art: [`docs/related-work.md`](../related-work.md) · Public disclosure:
[`docs/defensive-publication.md`](../defensive-publication.md).*
