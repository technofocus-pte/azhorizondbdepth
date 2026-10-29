# Lab 8: Monitoring and Operational Excellence for CartWise on Azure HorizonDB

**Estimated duration:** 60 minutes

## Scenario

CartWise is a fast-growing online retailer that sells home and lifestyle products to customers across several regions. Its storefront, order management and returns services all run on Azure HorizonDB. In Lab 7, the team launched a new returns service on a shared HorizonDB cluster, and the holiday shopping season is only weeks away.

**The problem.** Since the returns launch, order-tracking traffic has roughly doubled. This week, customers began complaining that the "track my order" page takes several seconds to load, and support tickets are piling up. The on-call engineer has no baseline to compare against and no clear answer to the first question of any incident: is the slowness caused by the cluster running out of resources, by an inefficient query, or by a session that is holding a lock?

**The solution.** CartWise needs an operational playbook for HorizonDB. You will play the role of the on-call engineer and build it end to end. You will establish a monitoring baseline and an alert in Azure Monitor, use pg_stat_statements to find the queries that consume the most time, fix them with the right indexes and prove the improvement with before-and-after numbers, diagnose a blocked session with live activity views, and keep tables healthy with pg_buffercache and pgstattuple. By the end of the lab, a slow page is no longer a mystery. It is a repeatable process: detect, locate, fix and verify.

## Objectives

After you complete this lab, you will be able to:

- Explore Azure HorizonDB platform metrics and create a metric alert in Azure Monitor.

- Identify slow and high-volume queries by using pg_stat_statements, and confirm a fix with before-and-after numbers.

- Find and resolve a blocking session by using pg_stat_activity.

- Inspect the buffer cache by using pg_buffercache, measure table bloat by using pgstattuple, and remove it by running vacuum.

- Verify the shared cluster from Lab 7, including its extensions and sample data, before you start troubleshooting.

## Exercise 0: Verify the shared cluster

In this exercise, you confirm that the cartwise database from Lab 7 is available and that the required extensions are loaded. Starting from a verified environment ensures that any problems you find later come from the workload, not from the setup.

1. In Visual Studio Code, connect to the **cartwise** database that you created in Lab 7.

    ![](media/image1.png)

2. Open a new query window and run the following queries one at a time:

    ```sql
    SELECT current_database();

    SHOW shared_preload_libraries;

    SELECT extname, extversion FROM pg_extension ORDER BY extname;

    SELECT (SELECT count(*) FROM retail.orders)  AS orders,
           (SELECT count(*) FROM retail.returns) AS returns;
    ```

3. Review the results. Confirm that the database meets all of the following conditions:

    - The `shared_preload_libraries` value includes **pg_cron** and **pg_stat_statements**.

    - The extension list includes **pg_stat_statements**, **pg_buffercache** and **pgstattuple**.

    - The orders and returns tables both contain rows.

    ![](media/image2.png)

## Exercise 1: Build the order-events workload

The order-tracking page reads from an event table that records every order status change. In this exercise, you create that table with one million rows and deliberately leave it without secondary indexes, exactly as it would have looked when the feature first shipped. You then create a script that imitates the CartWise application.

### Task 1: Create and load the order_events table

In this task, you create the order_events table and fill it with one million sample events spread across 90 days. This gives you a realistic data volume that makes missing indexes easy to see.

1. In the query window that is connected to the **cartwise** database, run the following statements:

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

    **Note:** The load can take up to a minute on 2 vCores. Wait for all statements to finish before you continue.

2. Verify that the row count is 1,000,000 and note the table size.

    ![](media/image3.png)

### Task 2: Create the workload script

In this task, you create a small Python script that behaves like the CartWise application. It repeatedly runs a dashboard count and a per-order tracking lookup, which are the two queries behind the slow page.

1. In Visual Studio Code, select **File explorer** \> **New file** \> **Python file**.

    ![](media/image4.png)

    ![](media/image5.png)

2. Enter the following code in the empty file, and then save it as **workload.py in documents folder**:

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

    ![](media/image6.png)

### Task 3: Reset statistics and generate the first load

In this task, you clear the query statistics so that your baseline contains only the workload you are about to run. You then run the script to simulate a busy period on the order-tracking page.

1. In Visual Studio Code, run the following statement in the query window to reset the query statistics:

    ```sql
    SELECT pg_stat_statements_reset();
    ```

    ![](media/image7.png)

2. Select three dots(…)-\>Terminal-\>new terminal.

    ![](media/image8.png)

3. In the terminal, navigate to the folder that contains the file.

    ```powershell
    +++cd documents+++
    ```

    ![](media/image9.png)

4. Set the connection details for the HorizonDB cluster by running the following commands:

    ```powershell
    $env:PGHOST:"<cluster-primary-endpoint>"
    $env:PGUSER="cartwise"
    $env:PGPASSWORD="Password@123!"
    ```

    **Note:** Replace `<cluster-primary-endpoint>` with the primary endpoint of your HorizonDB cluster. You can find it on the cluster **Overview** page in the Azure portal.

    ![](media/image10.png)

5. Run the workload by using the following command:

    ```powershell
    python workload.py
    ```

    ![](media/image11.png)

6. Wait for the script to print the **Done in** message, and then note the milliseconds per iteration. This is your baseline.

## Exercise 2: Azure Monitor metrics and an alert

Azure Monitor collects platform metrics for the cluster automatically, so you do not need to install anything to view them. In this exercise, you build a monitoring baseline for CartWise and configure an alert so that the on-call engineer is notified before customers notice a problem.

### Task 1: Explore metrics

In this task, you create four metric charts: CPU, memory, connections and storage. Together they form the baseline that every future incident will be compared against.

1. In the Azure portal, open your HorizonDB cluster: **cartwise-hdb-lab**.

2. In the left pane, under **Monitoring**, select **Metrics**.

    ![](media/image12.png)

3. Select **Local Time**, set **Time range** to **Last 30 minutes**, and then select **Apply**.

    ![](media/image13.png)

4. To add a chart for CPU, open the **Metric** drop-down list on the default chart, and then select **CPU utilization**.

    ![](media/image14.png)

    ![](media/image15.png)

5. Select **+ New chart** to add a chart for memory. In the **Metric** drop-down list, browse to and select the memory metric.

    ![](media/image16.png)

    ![](media/image17.png)

    ![](media/image18.png)

6. Select **+ New chart** again to add a chart for connections. In the **Metric** drop-down list, browse to and select **Active connections**.

    ![](media/image19.png)

    ![](media/image20.png)

    ![](media/image21.png)

7. Select **+ New chart** again to add a chart for storage. In the **Metric** drop-down list, browse to and select **Storage used**.

    ![](media/image22.png)

    ![](media/image23.png)

    ![](media/image24.png)

8. Return to Visual Studio Code, run `+++python workload.py+++` again, and then switch back to the Azure portal. Observe how the charts react while the workload runs.

    ![](media/image25.png)

    ![](media/image26.png)

    ![](media/image27.png)

    ![](media/image28.png)

    **Note:** The values you see might differ from the screenshots in this lab. This is expected, because they depend on the timing of your workload.

### Task 2: Check the activity log

In this task, you use the Logs experience to see whether recent connection problems might explain the customer complaints. Ruling out connection failures early saves the on-call engineer from investigating the wrong layer.

1. In the left pane, under **Monitoring**, select **Logs**.

    ![](media/image29.png)

    **Note:** Close any pop-up windows that appear.

2. In the query assistant box, enter the following prompt, and then press **Enter**:

    ```powershell
    +++Show recent errors+++
    ```

    Or you can select from the existing prompt.

    ![](media/image30.png)

3. Review the summary. It shows how many connections failed or succeeded.

    ![](media/image31.png)

    **Note:** The output is generated by AI, so it can vary from run to run.

### Task 3: Create an alert rule

In this task, you create an alert that emails the on-call engineer when CPU stays high. An alert turns monitoring from something you check into something that tells you when to act.

1. In the left pane, under **Monitoring**, select **Alerts**, and then select **Create** \> **Alert rule**.

    ![](media/image32.png)

2. On the **Condition** tab, open the **Signal name** drop-down list, and then select **See all signals**.

    ![](media/image33.png)

3. In the search box, enter `+++CPU+++`, select the **CPU Utilization** metric from the results, and then select **Apply**.

    ![](media/image34.png)

4. Configure the alert logic with the following values, and then select **Next**:

    - **Threshold:** Greater than 30 percent

    - **Aggregation type:** Average

    - **Check every:** 1 minute

    - **Lookback period:** 5 minutes

    **Note:** The low threshold is for this lab only. A production alert would normally use a value near 80 percent.

    ![](media/image35.png)

    ![](media/image36.png)

5. On the **Actions** tab, select **Use action groups** and then select **+Create action group**.

    ![](media/image37.png)

    ![](media/image38.png)

6. On the **Basics** tab, enter the following values and leave the remaining values at their defaults, and then select **Next**:

    - **Action group name:** cartwise-oncall

    - **Display name:** cartwise

    ![](media/image39.png)

7. On the **Notifications** tab, you create a notification that sends an email to your own address. In the **Notification type** drop-down list, select **Email/SMS message/Push/Voice**.

    ![](media/image40.png)

8. In the pane that opens, select **Email**, and then enter the following user name to receive the alert email: `+++@lab.CloudPortalCredential(User1).Username+++`. Select **OK**.

    ![](media/image41.png)

9. Enter a username for the notification, and then select **Review+create**.

    ![](media/image42.png)

10. Select Create.

    ![](media/image43.png)

11. Your action group is created.

    ![](media/image44.png)

12. Back on the alert rule wizard, select **Next** until you reach the **Details** tab. For **Alert rule name**, enter `+++cartwise-high-cpu+++`, and then select **Review + create**.

    ![](media/image45.png)

13. Select **Create**.

    ![](media/image46.png)

    The rule appears under **Alert rules**. Whether it fires depends on how hard your workload pushes the cluster, and firing is a bonus rather than a requirement. If it fires, the email and the alert entry show how the on-call engineer would be notified.

    ![](media/image47.png)

## Exercise 3: Find and fix slow queries

Metrics tell you that the database is busy. pg_stat_statements tells you which statements are responsible. In this exercise, you identify the queries behind the slow order-tracking page, find the root cause in the query plans, fix it with indexes, and prove the improvement under load.

### Task 1: Find the most expensive statements

In this task, you rank the statements that touch order_events by total execution time. The results become your "before" numbers.

1. In the query window, run the following query:

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

2. Confirm that both workload queries appear near the top of the results, and then record the `mean_ms` value for each.

    ![](media/image48.png)

    **Note:** pg_stat_statements groups statements by shape. The tracking lookup therefore appears once, with `$1` in place of the order number, no matter how many different orders were queried.

### Task 2: Look at the query plans

In this task, you use EXPLAIN to see how PostgreSQL runs each query. The plan shows why the queries are slow, not just that they are slow.

1. Run the following statements:

    ```sql
    EXPLAIN (ANALYZE, BUFFERS)
    SELECT count(*) FROM retail.order_events
    WHERE event_type = 'shipped' AND created_at > now() - interval '7 days';

    EXPLAIN (ANALYZE, BUFFERS)
    SELECT event_id, event_type, created_at FROM retail.order_events
    WHERE order_id = 1234 ORDER BY created_at;
    ```

    ![](media/image49.png)

2. Review both plans. Each plan shows a **Seq Scan** that reads the whole table. This is the root cause of the slow page. Note the execution time and the buffer counts for each plan.

    ![](media/image50.png)

### Task 3: Add the right indexes

In this task, you create one index for each query pattern. You use `CONCURRENTLY` so that production writes are not blocked while each index builds.

1. Run each of the following statements on its own. `CREATE INDEX CONCURRENTLY` cannot run inside a transaction block, so do not run the statements together as a batch.

    ```sql
    CREATE INDEX CONCURRENTLY idx_events_type_created
      ON retail.order_events (event_type, created_at);

    CREATE INDEX CONCURRENTLY idx_events_order_created
      ON retail.order_events (order_id, created_at);

    ANALYZE retail.order_events;
    ```

    ![](media/image51.png)

    ![](media/image52.png)

    ![](media/image53.png)

2. Run both `EXPLAIN (ANALYZE, BUFFERS)` statements from Task 2 again. You should now see index scans, much lower execution times and lower buffer counts.

    ![](media/image54.png)

    ![](media/image55.png)

### Task 4: Prove the fix under load

In this task, you rerun the workload and compare the results with your baseline. A fix is only complete when the numbers confirm it.

1. In the query window, reset the statistics:

    ```sql
    SELECT pg_stat_statements_reset();
    ```

    ![](media/image56.png)

2. In the terminal, run the workload again:

    ```powershell
    python workload.py
    ```

    ![](media/image57.png)

3. In the query window, run the Task 1 query again.

    Record the following three numbers, and compare them with your before numbers:

    - Dashboard query `mean_ms`

    - Tracking query `mean_ms`

    - Workload milliseconds per iteration

    All three numbers should drop noticeably, and the CPU chart in Azure Monitor should fall for the same period. This is the full loop of operational monitoring: **detect** (metric), **locate** (pg_stat_statements), **fix** (index) and **verify** (before and after).

    ![](media/image58.png)

## Exercise 4: Diagnose a blocked session

Not every slow request is a slow query. Sometimes a session is simply waiting for another session to release a lock. In this exercise, you create a blocking situation on the returns table and use live activity views to find the culprit. You need three query windows connected to the **cartwise** database. Call them **A** (the blocker), **B** (the victim) and **C** (you, the on-call engineer).

### Task 1: Create the problem

In this task, you simulate a common application bug: a transaction that updates a row and is never committed. A second session then tries to update the same row and has to wait.

1. In window **A**, open a transaction and leave it open:

    ```sql
    BEGIN;
    UPDATE retail.returns SET status = 'review' WHERE return_id = 1;
    ```

    ![](media/image59.png)

2. In window **B**, try to update the same row:

    ```sql
    UPDATE retail.returns SET refund_amount = refund_amount WHERE return_id = 1;
    ```

    This statement hangs, which is expected. Leave it running.

    ![](media/image60.png)

### Task 2: Diagnose the blocking session from window C

In this task, you use pg_stat_activity to identify who is waiting and who is causing the wait. This is the first thing an on-call engineer checks when a request seems stuck but the CPU looks normal.

1. In window **C**, run the following query:

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

    ![](media/image61.png)

2. Review the result. It shows the session from window B, a wait event type of **Lock**, and the process ID of the session that is blocking it. Copy the process ID from the `blocked_by` column.

    ![](media/image62.png)

    ![](media/image63.png)

3. Inspect the blocker by running the following query. Replace `<blocking-pid>` with the process ID that you copied:

    ```sql
    SELECT pid, state, xact_start, now() - xact_start AS open_for, left(query, 60) AS last_query
    FROM pg_stat_activity
    WHERE pid = <blocking-pid>;
    ```

    Notice that the blocker shows the state **idle in transaction**. It finished its statement but never committed, which is a classic application bug.

    ![](media/image64.png)

### Task 3: Resolve the blocking session

In this task, you end the blocking session so that the waiting request can complete. In a real incident where you cannot reach the owner of the session, this is the action you would take.

1. In window **C**, run the following statement. Replace `<blocking-pid>` with the process ID from Task 2:

    ```sql
    SELECT pg_terminate_backend(<blocking-pid>);
    ```

    ![](media/image65.png)

2. Switch to window **B** and confirm that the update has now completed.

    ![](media/image66.png)

## Exercise 5: Cache and bloat maintenance

Healthy operations include knowing what is in memory and keeping tables tidy. In this exercise, you inspect the buffer cache with pg_buffercache, create and measure table bloat with pgstattuple, and clean it up with vacuum.

### Task 1: Inspect the buffer cache

In this task, you see which tables and indexes occupy shared memory. This helps you tell whether a slow query is slow because its data is not cached.

1. Run the following query:

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

2. Review the results. The **order_events** table and its new indexes should dominate, because your workload keeps them hot.

    ![](media/image67.png)

### Task 2: Create bloat and measure it

In this task, you update many rows to leave dead row versions behind, and then measure them. Dead rows remain in the table until vacuum cleans them up.

1. Run the following statements:

    ```sql
    UPDATE retail.order_events
    SET payload = payload || '{"touched": true}'
    WHERE event_id <= 400000;

    SELECT * FROM pgstattuple_approx('retail.order_events');

    SELECT n_live_tup, n_dead_tup, last_autovacuum
    FROM pg_stat_user_tables
    WHERE relid = 'retail.order_events'::regclass;
    ```

2. In the output, review the **dead_tuple_percent** and **approx_free_percent** columns.

    ![](media/image68.png)

    ![](media/image69.png)

    **Note:** Autovacuum might already be working, so your numbers can differ from those of other participants.

### Task 3: Clean up and re-measure

In this task, you run a manual vacuum and measure the table again. This confirms that maintenance removes the dead rows.

1. Run the following statements:

    ```sql
    VACUUM (ANALYZE, VERBOSE) retail.order_events;

    SELECT * FROM pgstattuple_approx('retail.order_events');
    ```

    ![](media/image70.png)

2. Compare the results with Task 2. Dead tuples drop to near zero. Free space remains inside the table for reuse. Returning that space to the operating system requires a table rewrite, which is what pg_repack is for in production.

    ![](media/image71.png)

## Summary

In this lab, you acted as the on-call engineer for CartWise and turned a vague complaint about a slow "track my order" page into a structured investigation. You verified the shared cluster, built a one-million-row order-events workload, and used Azure Monitor to establish a baseline for CPU, memory, connections and storage, with an alert to notify the team when CPU runs high. You then used pg_stat_statements to locate the most expensive queries, confirmed with EXPLAIN that sequential scans were the root cause, added two concurrent indexes, and proved the improvement with before-and-after numbers. You also diagnosed a blocked session with pg_stat_activity and resolved it, inspected the buffer cache with pg_buffercache, and measured and removed table bloat with pgstattuple and vacuum. Together, these skills give CartWise a repeatable approach to detect, locate, fix and verify performance problems on Azure HorizonDB, so the team can head into the holiday season with confidence.
