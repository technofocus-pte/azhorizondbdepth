# Lab 8: Monitoring and Operational Excellence for CartWise on Azure HorizonDB

## Estimate Duration: 60 mins

## Scenario

CartWise's returns service is live, and order-tracking traffic is growing. This week, customers started complaining that the "track my order" page is slow, and the on-call engineer has no idea whether the cause is the database, a bad query or a locked row.

You are the on-call engineer. In this lab you will:

1. Build a monitoring baseline in Azure Monitor and create an alert.

2. Find the most expensive queries with **pg_stat_statements**, fix them, and prove the fix.

3. Diagnose a blocked session with live activity views.

4. Inspect cache and table health with **pg_buffercache** and **pgstattuple**, then automate maintenance with **pg_cron**.

## Objectives

After this lab you will be able to:

- Explore HorizonDB platform metrics and create a metric alert in Azure Monitor.

- Identify slow and high-volume queries with pg_stat_statements and confirm a fix with before and after numbers.

- Find and resolve a blocking session using pg_stat_activity.

- Measure table bloat with pgstattuple, run maintenance, and schedule it with pg_cron.

- Check the health of pg_durable workflows from Lab 8.

## Exercise 0: Verify the shared cluster

Connect to the **cartwise** database on cartwise-hdb-lab and run:

```sql
SELECT current_database();

SHOW shared_preload_libraries;

SELECT extname, extversion FROM pg_extension ORDER BY extname;

SELECT (SELECT count(*) FROM retail.orders)  AS orders,
       (SELECT count(*) FROM retail.returns) AS returns;

SELECT epoch_id, now() - last_seen_at AS time_since_last_heartbeat FROM df._worker_epoch;
```

**Checkpoint:**

- shared_preload_libraries includes pg_cron, pg_durable and pg_stat_statements.

- The extension list includes pg_durable, pg_stat_statements, pg_buffercache and pgstattuple.

- Orders and returns have rows, and the durable worker heartbeat is under 15 seconds.

If an extension is missing, run CREATE EXTENSION IF NOT EXISTS \<name\>;. If the allow-list rejects it, add the name to azure.extensions in the **cartwise-pg** parameter group.

## Exercise 1: Build the order-events workload

The order-tracking page reads from an event table that records every order status change. You create it with one million rows and deliberately **no secondary indexes**, as it would have looked when the feature first shipped.

### Step 1: Create and load the table

```sql
CREATE TABLE retail.order_events (
  event_id    bigserial PRIMARY KEY,
  order_id    int NOT NULL,
  event_type  text NOT NULL,
  payload     jsonb,
  created_at  timestamptz NOT NULL
);

INSERT INTO retail.order_events (order_id, event_type, payload, created_at)
SELECT 1 + (random() * 4999)::int,
       (ARRAY['placed','paid','packed','shipped','delivered'])[1 + (random() * 4)::int],
       jsonb_build_object('src', 'lab', 'n', g),
       now() - ((random() * 90)::int || ' days')::interval
            - ((random() * 86400)::int || ' seconds')::interval
FROM generate_series(1, 1000000) g;

ANALYZE retail.order_events;

SELECT count(*) FROM retail.order_events;
SELECT pg_size_pretty(pg_total_relation_size('retail.order_events')) AS table_size;
```

The load can take up to a minute on 2 vCores.

### Step 2: Create the workload script

Save this as **workload.py**. It mimics the app: a dashboard count and a per-order tracking lookup.

```python
import os, random, time
import psycopg

conn = psycopg.connect(
    host=os.environ["PGHOST"], dbname="cartwise",
    user=os.environ["PGUSER"], password=os.environ["PGPASSWORD"],
    sslmode="require", autocommit=True,
)
cur = conn.cursor()

DASHBOARD = ("SELECT count(*) FROM retail.order_events "
             "WHERE event_type = 'shipped' AND created_at > now() - interval '7 days'")
TRACKING = ("SELECT event_id, event_type, created_at FROM retail.order_events "
            "WHERE order_id = %s ORDER BY created_at")

N = int(os.environ.get("ITERATIONS", "150"))
start = time.time()
for i in range(N):
    cur.execute(DASHBOARD)
    cur.fetchall()
    cur.execute(TRACKING, (random.randint(1, 5000),))
    cur.fetchall()
    if (i + 1) % 25 == 0:
        print(f"{i + 1}/{N} iterations, {time.time() - start:.0f}s elapsed")
print(f"Done in {time.time() - start:.1f}s ({(time.time() - start) / N * 1000:.0f} ms per iteration)")
conn.close()
```

### Step 3: Reset statistics and generate the first load

In Visual Studio Code, reset the query statistics so your baseline is clean:

```sql
SELECT pg_stat_statements_reset();
```

Then run the workload in a terminal and note the time per iteration. Leave it running while you start Exercise 2.

```bash
python workload.py
```

**Checkpoint:** the script completes and reports a per-iteration time. Write this number down as your **baseline**.

## Exercise 2: Azure Monitor metrics and an alert

Azure Monitor collects platform metrics for the cluster automatically. You do not install anything to view them.

### Step 1: Explore metrics

1. In the Azure portal, open **cartwise-hdb-lab**.

2. Under **Monitoring**, select **Metrics**.

3. Set the time range to the **last 30 minutes**.

4. Add a chart for a **CPU utilization** metric. Use the Metric drop-down to browse what is available for your cluster.

5. Add further charts for **memory**, **active connections** and **storage or I/O** metrics.

6. Run workload.py again (or a second copy in another terminal) and watch the charts react.

    > Metric names in the picker can differ slightly in Preview. Choose the closest CPU, memory, connection and I/O metrics your cluster lists.

You are looking for one habit: **always read a metric alongside the activity that caused it**. A CPU spike tells you something is wrong, and the next exercise tells you what.

### Step 2: Check the activity log

Open **Activity log** on the cluster. Find the operations from Lab 8 (cluster creation, parameter group changes, restart). The activity log answers "who changed what and when", while metrics answer "how is it behaving".

### Step 3: Create an alert rule

1. Under **Monitoring**, select **Alerts**, then **Create** and **Alert rule**.

2. For the condition, select the **CPU utilization** metric. Set the threshold to **greater than 30 percent**, aggregated as average over **5 minutes**, evaluated every minute. The low threshold is for the lab only. A production alert would normally sit near 80 percent.

3. Create a new **action group** named **cartwise-oncall** with an **Email** notification to your own address.

4. Name the rule **cartwise-high-cpu** and create it.

**Checkpoint:** the rule appears under **Alert rules**. Whether it fires depends on how hard your workload pushes the cluster, and firing is a bonus rather than a requirement. If it fires, the email and the alert entry show how the on-call engineer would be notified.

## Exercise 3: Find and fix slow queries (16 minutes)

Metrics tell you the database is busy. **pg_stat_statements** tells you which statements are responsible.

### Step 1: Find the most expensive statements

```sql
SELECT left(query, 80)                         AS query,
       calls,
       round(total_exec_time::numeric, 0)      AS total_ms,
       round(mean_exec_time::numeric, 2)       AS mean_ms,
       shared_blks_read                        AS blocks_read
FROM pg_stat_statements
WHERE dbid = (SELECT oid FROM pg_database WHERE datname = 'cartwise')
  AND query ILIKE '%order_events%'
ORDER BY total_exec_time DESC
LIMIT 5;
```

Both workload queries should appear near the top. Record the **mean_ms** for each. These are your before numbers.

> pg_stat_statements groups statements by shape, so the tracking lookup appears once with \$1 in place of the order number, regardless of how many different orders were queried.

### Step 2: Look at the plans

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) FROM retail.order_events
WHERE event_type = 'shipped' AND created_at > now() - interval '7 days';

EXPLAIN (ANALYZE, BUFFERS)
SELECT event_id, event_type, created_at FROM retail.order_events
WHERE order_id = 1234 ORDER BY created_at;
```

Both plans should show a **Seq Scan** that reads the whole table. That is the root cause.

### Step 3: Add the right indexes

Use CONCURRENTLY so production writes are not blocked while the index builds. It cannot run inside a transaction block, so run each statement on its own.

```sql
CREATE INDEX CONCURRENTLY idx_events_type_created
  ON retail.order_events (event_type, created_at);
```

```sql
CREATE INDEX CONCURRENTLY idx_events_order_created
  ON retail.order_events (order_id, created_at);
```

```sql
ANALYZE retail.order_events;
```

Re-run both EXPLAIN (ANALYZE, BUFFERS) statements. You should now see index scans and much lower execution times and buffer counts.

### Step 4: Prove the fix under load

Reset the statistics, run the workload again, and compare:

```sql
SELECT pg_stat_statements_reset();
```

```bash
python workload.py
```

Then run the Step 1 query again and measure Dashboard query mean_ms, Tracking query mean_ms and Workload ms per iteration

**All** three numbers drop noticeably, and the CPU chart in Azure Monitor falls for the same period. That is the full loop of operational monitoring: **detect** (metric), **locate** (pg_stat_statements), **fix** (index), **verify** (before and after).

## Exercise 4: Diagnose a blocked session

Not every slow request is a slow query. Sometimes a session is simply waiting. You need **three query windows** connected to the cartwise database. Call them **A** (the blocker), **B** (the victim) and **C** (you, the on-call engineer).

### Step 1: Create the problem

In window **A**, open a transaction and leave it open:

```sql
BEGIN;
UPDATE retail.returns SET status = 'review' WHERE return_id = 1;
```

In window **B**, try to update the same row. This statement will hang, which is expected:

```sql
UPDATE retail.returns SET refund_amount = refund_amount WHERE return_id = 1;
```

### Step 2: Diagnose it from window C

```sql
SELECT pid,
       pg_blocking_pids(pid)                  AS blocked_by,
       state,
       wait_event_type,
       wait_event,
       now() - query_start                    AS waiting_for,
       left(query, 60)                        AS query
FROM pg_stat_activity
WHERE datname = 'cartwise'
  AND cardinality(pg_blocking_pids(pid)) > 0;
```

The result shows window B's session, a wait event type of **Lock**, and the process ID of the session blocking it. Now look at the blocker:

```sql
SELECT pid, state, xact_start, now() - xact_start AS open_for, left(query, 60) AS last_query
FROM pg_stat_activity
WHERE pid = <blocking-pid>;
```

The blocker shows **idle in transaction**. It finished its statement but never committed, which is a classic application bug.

### Step 3: Resolve it

Prefer the least destructive option first. In window **A**, run ROLLBACK; and watch window B complete immediately.

In a real incident where you cannot reach the owner of the session, you would use this from window C instead (replace the pid):

```sql
SELECT pg_terminate_backend(<blocking-pid>);
```

**Checkpoint:** re-run the diagnostic query in window C. It returns no rows.

## Exercise 5: Cache, bloat and automated maintenance (10 minutes)

### Step 1: What is in the buffer cache?

```sql
SELECT c.relname,
       count(*)                                  AS buffers,
       pg_size_pretty(count(*) * 8192)           AS cached
FROM pg_buffercache b
JOIN pg_class c
  ON b.relfilenode = pg_relation_filenode(c.oid)
 AND b.reldatabase IN (0, (SELECT oid FROM pg_database WHERE datname = current_database()))
WHERE c.relnamespace = 'retail'::regnamespace
GROUP BY c.relname
ORDER BY buffers DESC
LIMIT 5;
```

The order_events table and its new indexes should dominate, because your workload keeps them hot. This is how you tell whether a slow query is slow because its data is not cached.

### Step 2: Create bloat and measure it

Updating many rows leaves dead row versions behind until vacuum cleans them.

```sql
UPDATE retail.order_events
SET payload = payload || '{"touched": true}'
WHERE event_id <= 400000;

SELECT * FROM pgstattuple_approx('retail.order_events');

SELECT n_live_tup, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables
WHERE relid = 'retail.order_events'::regclass;
```

Look at the **dead_tuple_percent** and **approx_free_percent** columns. Autovacuum may already be working, so your numbers can differ from a neighbour's.

### Step 3: Clean up and re-measure

```sql
VACUUM (ANALYZE, VERBOSE) retail.order_events;

SELECT * FROM pgstattuple_approx('retail.order_events');
```

Dead tuples drop to near zero. Free space remains inside the table for reuse. Returning that space to the operating system needs a table rewrite, which is what pg_repack is for in production.
