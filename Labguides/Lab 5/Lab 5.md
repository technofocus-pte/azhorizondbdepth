# Lab 5 — Optimize Vector Search at Scale with DiskANN on Azure HorizonDB

## Scenario

The legal research agent from Lab 5 works well with 12 documents. Calder & Voss now plans to index its whole research library: court opinions from several jurisdictions, thousands of firm memos and years of matter files, split into millions of text passages. At that size, comparing the question against every stored vector is too slow, and many associates will ask questions at the same time.

You are the platform engineer. You will prove what a DiskANN index does for this workload and decide how to configure it. You will not guess: you measure the plan, the recall and the latency under load.

The benchmark data is synthetic. It is generated from the 12 real document embeddings by adding random variation, so it has the same structure as real data (clusters of similar text) and is large enough to show index behavior. The numbers are for learning and do not predict production results.

## Learning objectives

After this lab you can:

1. Generate a benchmark table that behaves like a real vector workload.
2. Read an `EXPLAIN ANALYZE` plan to tell a sequential scan from an index scan.
3. Create a DiskANN index and explain its build parameters.
4. Measure recall against exact results and tune `diskann.l_value_is`.
5. Run a concurrent load test and compare exact search with indexed search.
6. Explain why filtered vector search can return too few rows, and how iterative search fixes it.


## Exercise 0: Check the environment 

Connect to `legalai_lab` and run:

```sql
SELECT COUNT(*) AS documents, COUNT(embedding) AS embedded FROM legal.documents;

SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'pg_diskann');

SHOW diskann.l_value_is;
```

**Expected result:** 12 and 12, both extensions listed, and a value for `diskann.l_value_is` (the search list size, 100 by default). If a check fails, complete the missing part of Lab 5 first.

## Exercise 1: Build a realistic benchmark dataset 

### Task 1: Create a function that adds random variation to a vector

```sql
CREATE OR REPLACE FUNCTION legal.noisy_vec(base vector, noise double precision DEFAULT 0.04)
RETURNS vector
LANGUAGE sql VOLATILE
AS $$
    SELECT ARRAY(
        SELECT (u.b + (random() - 0.5) * noise)::real
        FROM unnest(base::real[]) WITH ORDINALITY AS u(b, ord)
        ORDER BY u.ord
    )::vector
$$;
```

### Task 2: Generate 30,000 passages

Each document becomes 2,500 slightly different passages. Unlike copies of the same vector, these passages have different distances, so the index has real work to do.

```sql
CREATE TABLE legal.bench_chunks (
    chunk_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id    text NOT NULL,
    doc_type  text NOT NULL,
    embedding vector(1536) NOT NULL
);

INSERT INTO legal.bench_chunks (doc_id, doc_type, embedding)
SELECT d.doc_id, d.doc_type, legal.noisy_vec(d.embedding)
FROM legal.documents AS d
CROSS JOIN generate_series(1, 2500) AS n;

ANALYZE legal.bench_chunks;

SELECT COUNT(*) AS passages, pg_size_pretty(pg_table_size('legal.bench_chunks')) AS table_size
FROM legal.bench_chunks;
```

**Expected result:** 30,000 passages. The insert takes one to three minutes on 2 to 4 vCores. If it is too slow in your environment, change `2500` to `1000` and note that the speed-up from the index will be smaller.

### Task 3: Create test queries and exact answers

Create 24 query vectors (two per document, with more variation than the stored passages), then record the exact top 10 for each. This is the ground truth for measuring recall. Do this before you create the index so the answers come from a full scan.

```sql
CREATE TABLE legal.bench_queries AS
SELECT ROW_NUMBER() OVER (ORDER BY d.doc_id, n) AS qid,
       legal.noisy_vec(d.embedding, 0.06) AS embedding
FROM legal.documents AS d
CROSS JOIN generate_series(1, 2) AS n;

CREATE TABLE legal.bench_truth AS
SELECT q.qid, t.chunk_id
FROM legal.bench_queries AS q
CROSS JOIN LATERAL (
    SELECT c.chunk_id
    FROM legal.bench_chunks AS c
    ORDER BY c.embedding <=> q.embedding
    LIMIT 10
) AS t;

SELECT COUNT(*) AS queries FROM legal.bench_queries;
SELECT COUNT(*) AS truth_rows FROM legal.bench_truth;
```

**Expected result:** 24 queries and 240 truth rows.

**Checkpoint:** You have a 30,000-row table, 24 test queries, and the exact nearest neighbors for each.

## Exercise 2: Baseline, DiskANN index and query plan (12 minutes)

### Task 1: Measure the baseline without an index

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT chunk_id, doc_id
FROM legal.bench_chunks
ORDER BY embedding <=> (SELECT embedding FROM legal.bench_queries WHERE qid = 1)
LIMIT 10;
```

In the plan, find and write down:

- The scan type (expect `Seq Scan`, with a `Sort` or top-N heapsort above it).
- `Execution Time` at the bottom.
- The `Buffers` line: how many pages were read.

### Task 2: Create the DiskANN index

```sql
CREATE INDEX idx_bench_diskann
ON legal.bench_chunks
USING diskann (embedding vector_cosine_ops)
WITH (max_neighbors = 32, l_value_ib = 100);

ANALYZE legal.bench_chunks;
```

The index build takes one to four minutes. The two options control the index graph:

| Option | Meaning | Effect of a higher value |
|---|---|---|
| `max_neighbors` | Maximum edges per node (default 32) | Can improve recall, uses more space |
| `l_value_ib` | Search list size while building (default 100) | Better index quality, slower build |

While it builds, discuss with your instructor: why is an approximate index useful when an exact scan is always correct? A missed precedent matters in legal research, which is why you will measure recall.

### Task 3: Compare the plan

Run the same `EXPLAIN ANALYZE` again:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT chunk_id, doc_id
FROM legal.bench_chunks
ORDER BY embedding <=> (SELECT embedding FROM legal.bench_queries WHERE qid = 1)
LIMIT 10;
```

**Expected result:** an `Index Scan` using `idx_bench_diskann`, with an `Execution Time` well below the baseline. The exact numbers depend on your compute size.

If you still see a `Seq Scan`, the planner decided it was cheaper. Check that `ANALYZE` ran, then test the index explicitly inside a transaction:

```sql
BEGIN;
SET LOCAL enable_seqscan = off;
EXPLAIN (ANALYZE, BUFFERS)
SELECT chunk_id, doc_id
FROM legal.bench_chunks
ORDER BY embedding <=> (SELECT embedding FROM legal.bench_queries WHERE qid = 1)
LIMIT 10;
COMMIT;
```

**Note:** Forcing the plan is a diagnostic. In production, find out why the planner chose a scan, and do not force it as a fix.

### Task 4: Check the size cost

```sql
SELECT pg_size_pretty(pg_table_size('legal.bench_chunks')) AS table_size,
       pg_size_pretty(pg_relation_size('legal.idx_bench_diskann')) AS index_size;
```

Record both sizes. An index is a trade-off: faster queries for more storage and slower writes.

**Checkpoint:** You have a baseline time, an indexed time, and the size of the index.

## Exercise 3: Tune the recall and latency trade-off 

An approximate index may miss some true neighbors. Recall is the share of the exact top 10 that the index also returns. At query time, `diskann.l_value_is` sets how many candidates the search keeps: a larger value gives higher recall and slower queries.

### Task 1: Create `bench.py`

In the folder where you keep the agent from Lab 5 (with the virtual environment active), create `bench.py`:

```python
import argparse
import concurrent.futures as cf
import os
import statistics
import time

import psycopg

DSN = os.environ['HORIZONDB_DSN']
ANN_SQL = '''SELECT chunk_id FROM legal.bench_chunks
ORDER BY embedding <=> %s::vector LIMIT 10'''


def load_queries(conn):
    rows = conn.execute('SELECT qid, embedding::text FROM legal.bench_queries ORDER BY qid').fetchall()
    return [(r[0], r[1]) for r in rows]


def load_truth(conn):
    truth = {}
    for qid, chunk_id in conn.execute('SELECT qid, chunk_id FROM legal.bench_truth').fetchall():
        truth.setdefault(qid, set()).add(chunk_id)
    return truth


def tune(l_values):
    with psycopg.connect(DSN, autocommit=True) as conn:
        queries = load_queries(conn)
        truth = load_truth(conn)
        print('l_value_is | recall@10 | avg ms | p95 ms')
        for l_value in l_values:
            conn.execute(f'SET diskann.l_value_is = {int(l_value)}')
            hits, total, times = 0, 0, []
            for qid, emb in queries:
                start = time.perf_counter()
                ids = {r[0] for r in conn.execute(ANN_SQL, (emb,)).fetchall()}
                times.append((time.perf_counter() - start) * 1000)
                hits += len(ids & truth[qid])
                total += len(truth[qid])
            times.sort()
            p95 = times[max(0, int(len(times) * 0.95) - 1)]
            print(f'{l_value:>10} | {100 * hits / total:>8.1f}% | {statistics.mean(times):>6.1f} | {p95:>6.1f}')


def worker(mode, l_value, queries, offset, stop_at):
    latencies = []
    with psycopg.connect(DSN, autocommit=True) as conn:
        if mode == 'exact':
            conn.execute('SET enable_indexscan = off')
        else:
            conn.execute(f'SET diskann.l_value_is = {int(l_value)}')
        i = offset
        while time.time() < stop_at:
            emb = queries[i % len(queries)][1]
            start = time.perf_counter()
            conn.execute(ANN_SQL, (emb,)).fetchall()
            latencies.append((time.perf_counter() - start) * 1000)
            i += 1
    return latencies


def load(mode, l_value, thread_counts, seconds):
    with psycopg.connect(DSN, autocommit=True) as conn:
        queries = load_queries(conn)
    print(f'mode={mode} l_value_is={l_value}')
    print('threads |   QPS | p50 ms | p95 ms')
    for threads in thread_counts:
        stop_at = time.time() + seconds
        with cf.ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [pool.submit(worker, mode, l_value, queries, n * 3, stop_at) for n in range(threads)]
            latencies = sorted(x for f in futures for x in f.result())
        qps = len(latencies) / seconds
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
        print(f'{threads:>7} | {qps:>5.1f} | {p50:>6.1f} | {p95:>6.1f}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    tune_parser = sub.add_parser('tune')
    tune_parser.add_argument('--l', type=int, nargs='+', default=[10, 20, 50, 100, 200, 400])
    load_parser = sub.add_parser('load')
    load_parser.add_argument('--mode', choices=['ann', 'exact'], default='ann')
    load_parser.add_argument('--l-value', type=int, default=100)
    load_parser.add_argument('--threads', type=int, nargs='+', default=[1, 4, 8])
    load_parser.add_argument('--seconds', type=int, default=8)
    args = parser.parse_args()
    if args.cmd == 'tune':
        tune(args.l)
    else:
        load(args.mode, args.l_value, args.threads, args.seconds)
```

### Task 2: Run the tuning sweep

```bash
python bench.py tune
```

The script runs the 24 test queries at each `l_value_is` setting and compares the results with the exact answers you stored in `legal.bench_truth`. Copy the output into this table:

| `l_value_is` | Recall@10 | Average (ms) | p95 (ms) |
|---:|---:|---:|---:|
| 10 |  |  |  |
| 20 |  |  |  |
| 50 |  |  |  |
| 100 |  |  |  |
| 200 |  |  |  |
| 400 |  |  |  |

**Expected pattern:** recall rises as `l_value_is` rises, and latency rises with it. The values will differ in your environment.

### Task 3: Choose a setting

Agree a recall target with your instructor, for example 95 percent. Pick the smallest `l_value_is` that meets it. Explain your choice in one sentence: what would you lose by choosing 400 for a latency-sensitive chat agent, and what would you lose by choosing 10 for a search that must not miss a controlling precedent?

### Task 4 (optional): Change the index build settings

Build a second index with a larger graph, repeat the sweep, and compare recall, latency and size. Drop the old index first so the planner uses the new one.

```sql
DROP INDEX legal.idx_bench_diskann;

CREATE INDEX idx_bench_diskann
ON legal.bench_chunks
USING diskann (embedding vector_cosine_ops)
WITH (max_neighbors = 64, l_value_ib = 200);
```

**Checkpoint:** You can state the recall and latency for each search list size, and you have chosen a setting based on a measured result.

## Exercise 4: Load test and filtered search 

### Task 1: Exact search under concurrent load

This run disables the index and measures exact search with 1 and 4 simultaneous clients, each running for 8 seconds.

```bash
python bench.py load --mode exact --threads 1 4
```

Record queries per second (QPS) and the p95 latency. Exact search slows down quickly as clients are added.

### Task 2: Indexed search under concurrent load

Use the `l_value_is` you chose in Exercise 3.

```bash
python bench.py load --mode ann --l-value 100 --threads 1 4 8
```

| Mode | Threads | QPS | p95 (ms) |
|---|---:|---:|---:|
| exact | 1 |  |  |
| exact | 4 |  |  |
| ann | 1 |  |  |
| ann | 4 |  |  |
| ann | 8 |  |  |

**Expected result:** the indexed search handles many times more queries per second at a much lower p95 than exact search, and stays steadier as clients are added.

**Note:** If your cluster has a read replica, point `HORIZONDB_DSN` at the replica endpoint and run the indexed test again. Read replicas add search capacity without extra load on the primary. This cluster has high availability disabled, so this step is optional.

### Task 3: Filtered vector search

Real applications combine vector search with filters such as document type. Query 1 is closest to CASE-001, a court opinion. Ask for 50 passages from firm memos only:

```sql
SET diskann.l_value_is = 100;

-- Non-iterative search: only one batch of candidates is examined, then filtered
SET diskann.iterative_search = 'off';
SELECT COUNT(*) AS rows_returned FROM (
    SELECT chunk_id
    FROM legal.bench_chunks
    WHERE doc_type = 'MEMO'
    ORDER BY embedding <=> (SELECT embedding FROM legal.bench_queries WHERE qid = 1)
    LIMIT 50
) AS t;

-- Iterative search: keeps walking the graph until 50 rows match
SET diskann.iterative_search = 'relaxed_order';
SELECT COUNT(*) AS rows_returned FROM (
    SELECT chunk_id
    FROM legal.bench_chunks
    WHERE doc_type = 'MEMO'
    ORDER BY embedding <=> (SELECT embedding FROM legal.bench_queries WHERE qid = 1)
    LIMIT 50
) AS t;
```

**Expected result:** the first query returns far fewer than 50 rows, possibly none, because the nearest 100 candidates are almost all passages of the court opinion and the filter removes them. The second returns 50. The `relaxed_order` mode may return results slightly out of distance order. If you need strict ordering, test `SET diskann.iterative_search = 'strict_order'`.

**Why this matters:** the same effect appears with row-level security in Lab 7, because security filters work like `WHERE` clauses. A lawyer who sees too few results may wrongly believe that no authority exists.

### Task 4: Reset the session settings

```sql
RESET diskann.l_value_is;
RESET diskann.iterative_search;
```

**Checkpoint:** You compared exact and indexed search under load, and you saw how a filter can starve an approximate search.

## Validate your results

- [ ] Created 30,000 benchmark passages, 24 test queries and 240 truth rows.
- [ ] Recorded the baseline plan (`Seq Scan`) and its execution time.
- [ ] Created the DiskANN index and confirmed an `Index Scan` in the plan.
- [ ] Recorded the table size and the index size.
- [ ] Completed the recall and latency table for at least four `l_value_is` values.
- [ ] Chose a setting and gave one reason.
- [ ] Compared exact and indexed QPS and p95 latency under load.
- [ ] Showed that non-iterative filtered search returns too few rows, and that iterative search fixes it.

