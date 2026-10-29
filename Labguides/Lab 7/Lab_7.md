# Lab 7: CartWise Returns Automation with Extensions, Scheduled Jobs and App Integration

**Estimated duration:** 60 minutes

## Scenario

CartWise Retail is an online retailer that sells electronics, sports gear, apparel, beauty products and home goods. It processes thousands of orders a day through its web and mobile apps, and roughly one in eight orders comes back as a return request. Each request carries flexible details, such as the reason and the channel it came from, and those details differ from one request to the next.

**The problem.** The returns process has outgrown the way it was built. Managers approve returns by email, so two managers can answer the same request, or nobody answers at all. Requests that no one answers never expire, so customers wait with no outcome. The nightly returns summary is refreshed by hand and is often out of date. Customers who mistype a product name in the search box see no results, and they leave. Each of these problems has a different workaround, and none of the workarounds is reliable.

**The solution.** As the platform developer, you move this work into Azure HorizonDB and expose it to applications. You use PostgreSQL extensions to search products with typos (pg_trgm), query flexible JSONB return data, and run recurring jobs (pg_cron). You put the approval rules inside the database as a transactional function, so no client can bypass them, expire stale requests on a schedule, and publish events with LISTEN and NOTIFY. Finally, you expose everything through a REST API written in Python, using a standard PostgreSQL driver and a connection pool. The lab also creates the **cartwise** database that you reuse in Lab 8.

## Objectives

After you complete this lab, you will be able to:

- Deploy an Azure HorizonDB cluster and enable extensions by using a parameter group.

- Allow, preload and create extensions, and know which ones need a restart.

- Use pg_trgm for fuzzy search and a GIN index for JSONB queries.

- Schedule recurring jobs with pg_cron, including jobs that run in another database.

- Implement approval rules as a PL/pgSQL function, and publish events with a trigger and pg_notify.

- Build a REST API on HorizonDB by using Python, FastAPI and a connection pool.

## Exercise 0: Lab setup

In this exercise, you deploy the HorizonDB cluster and attach a parameter group that allows and preloads the extensions the lab needs. Extensions must be allow-listed and, for some, preloaded before you can create them in a database.

### Task 1: Configure and deploy an Azure HorizonDB cluster

In this task, you create a two-vCore HorizonDB cluster in the Azure portal.

1. Open a web browser and go to `+++https://portal.azure.com/+++`.

2. Sign in to the Azure portal with the following credentials:

    - **Username:** `+++@lab.CloudPortalCredential(User1).Username+++`

    - **TAP Token:** `+++@lab.CloudPortalCredential(User1).AccessToken+++`

    ![A screenshot of a sign in box  AI-generated content may be incorrect.](media/image1.png)

    ![A screenshot of a login screen  AI-generated content may be incorrect.](media/image2.png)

    ![A screenshot of a computer  AI-generated content may be incorrect.](media/image3.png)

3. In the search box at the top of the page, enter `+++Azure HorizonDB+++`. Under **Services**, select **Azure HorizonDB**.

    ![](media/image4.png)

4. Select **Create**.

    ![A screenshot of a computer  AI-generated content may be incorrect.](media/image5.png)

5. On the **Basics** tab, enter the values in the following table. Leave all other settings at their defaults, and then select **Next**.

    | **Setting** | **Value** |
    |---|---|
    | Subscription | Your lab subscription |
    | Resource group | ResourceGroup1 |
    | Cluster name | cartwise@lab.LabInstance.Id |
    | Region | Central US |
    | PostgreSQL version | 17 |
    | vCores | 2 |
    | High availability | Disabled |
    | Authentication | PostgreSQL authentication |
    | Admin username | cartwise |
    | Admin password | Password@123! |

    ![](media/image6.png)

    ![](media/image7.png)

    ![](media/image8.png)

6. On the **Networking** tab, under **Firewall rules**, select **Allow public access from any Azure service within Azure to this cluster**.

    ![](media/image9.png)

7. Select **Add current client IP address** to add your public IP address to the firewall rules, and then select **Review + create**.

    ![](media/image10.png)

8. Review the summary, and then select **Create**.

    ![](media/image11.png)

9. Wait for the deployment to finish. This takes about 10 to 15 minutes.

10. When the deployment completes, select **Go to resource group**, and then open the newly created HorizonDB cluster.

### Task 2: Create the parameter group and allow-list the extensions

In this task, you create a parameter group that allows five extensions and preloads two of them. Preloaded libraries are static parameters, so the cluster restarts when you attach the group.

1. In the Azure portal, open the cluster **cartwise@lab.LabInstance.Id**, and then select **Settings** \> **Parameters**. Next to **Parameter group**, select **(create)**.

    ![](media/image12.png)

2. On the **Create a parameter group** page, enter the following values, and then select **Next**.

    | **Setting** | **Value** |
    |---|---|
    | Subscription | Your lab subscription |
    | Resource group | ResourceGroup1 |
    | Parameter group name | cartwise-pg |
    | Region | Central US (must match the cluster) |
    | PostgreSQL version | 17 |
    | Parameter group (base) | PostgreSQL 17 |

    ![](media/image13.png)

3. On the parameters page, filter for `+++azure.extensions+++`. In the parameter drop-down list, select the following values: **pg_cron**, **pg_trgm**, **pg_stat_statements**, **pg_buffercache** and **pgstattuple**.

    ![](media/image14.png)

4. Search for `+++shared_preload_libraries+++`. In the drop-down list, select **pg_cron** and **pg_stat_statements**.

    ![](media/image15.png)

5. Search for `+++pg_stat_statements.track+++`, and set the value to **top**. Then select **Create**.

    ![](media/image16.png)

6. Select **Go to resource**, and then open the HorizonDB cluster.

    **Note:** The deployment takes 4 to 5 minutes to complete.

7. Select **Settings** \> **Parameters**, and then select **(change)** next to **Parameter group**.

    ![](media/image17.png)

8. Select **cartwise-pg**, and then select **Save**. Because the parameters are static, the cluster restarts automatically when you attach the group.

    ![](media/image18.png)

9. On the **Parameters** page, select **Refresh**, and then confirm that the parameter group is **cartwise-pg**.

    ![](media/image19.png)

10. Go to the **Overview** page, and then copy and save the **Primary endpoint** value. You use it in the exercises that follow.

    ![](media/image20.png)

## Exercise 1: Create the CartWise database, extensions and data

In this exercise, you create the cartwise database, enable the extensions, and load a realistic retail data set. Everything you build in the rest of this lab, and in Lab 8, runs against this database.

### Task 1: Connect and create the database

In this task, you connect to the cluster from Visual Studio Code and create an empty cartwise database. You then open a second connection that points to the new database.

1. Open Visual Studio Code, and then select the **PostgreSQL** extension.

    **Note:** If the PostgreSQL extension isn't available, select **Extensions**, search for `PostgreSQL`, and then select **Install**.

    ![](media/image21.png)

2. Select **+ Add connection**.

    ![](media/image22.png)

3. Enter the following connection details:

    | **Setting** | **Suggested value** |
    |---|---|
    | Server name | The primary endpoint that you saved in Exercise 0, Task 2, step 10 |
    | Authentication Type | Password |
    | Admin username | cartwise |
    | Admin password | Password@123! |
    | Connection Name | PostgresDB |
    | Server Group | Servers |

    ![](media/image23.png)

4. Select **Test connection**. After the test succeeds, select **Save & Connect**.

    ![](media/image24.png)

    ![](media/image25.png)

5. Select **New Query**.

    ![](media/image26.png)

6. Enter the following command, and then select the **Play** button to run it:

    ```powershell
    +++CREATE DATABASE cartwise+++
    ```

    ![](media/image27.png)

    Your new database is created.

7. Select **Add a new connection** to create a connection that uses cartwise as its database.

    ![](media/image28.png)

8. Enter the following details:

    | **Setting** | **Suggested value** |
    |---|---|
    | Server name | The primary endpoint that you saved in Exercise 0, Task 2, step 10 |
    | Authentication Type | Password |
    | Admin username | cartwise |
    | Admin password | Password@123! |
    | Database | cartwise |
    | Server Group | Servers |

    ![](media/image29.png)

    ![](media/image30.png)

9. Select **Test Connection**. After the test succeeds, select **Save & Connect**.

    ![](media/image31.png)

    ![](media/image32.png)

### Task 2: Create the extensions

In this task, you create four extensions in the cartwise database. Allow-listing an extension in the parameter group makes it available, but you still have to create it in each database that uses it.

1. Select New Query.

    ![](media/image33.png)

2. In a new query window that is connected to the **cartwise** database, run the following commands:

    ```sql
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    CREATE EXTENSION IF NOT EXISTS pg_buffercache;
    CREATE EXTENSION IF NOT EXISTS pgstattuple;

    SELECT extname, extversion FROM pg_extension ORDER BY extname;
    ```

    Confirm that the result lists all four extensions.

    ![](media/image34.png)

### Task 3: Create the schema

In this task, you create the retail schema and the five tables that hold products, orders, returns, summary statistics and an operations log. The returns table stores its flexible details in a JSONB column.

1. Run the following commands to create the schema and tables:

    ```sql
    CREATE SCHEMA IF NOT EXISTS retail;

    CREATE TABLE retail.products (
      product_id  serial PRIMARY KEY,
      name        text NOT NULL,
      category    text NOT NULL,
      price       numeric(10,2) NOT NULL
    );

    CREATE TABLE retail.orders (
      order_id    serial PRIMARY KEY,
      product_id  int NOT NULL REFERENCES retail.products(product_id),
      customer_id int NOT NULL,
      qty         int NOT NULL,
      order_total numeric(10,2) NOT NULL,
      ordered_at  timestamptz NOT NULL
    );

    CREATE TABLE retail.returns (
      return_id     serial PRIMARY KEY,
      order_id      int NOT NULL REFERENCES retail.orders(order_id),
      status        text NOT NULL DEFAULT 'requested',
      refund_amount numeric(10,2) NOT NULL,
      metadata      jsonb NOT NULL,
      requested_at  timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE retail.return_stats (
      category      text,
      reason        text,
      return_count  int,
      refunded      numeric(12,2),
      refreshed_at  timestamptz DEFAULT now()
    );

    CREATE TABLE retail.ops_log (
      log_id     serial PRIMARY KEY,
      job        text,
      detail     text,
      logged_at  timestamptz DEFAULT now()
    );
    ```

    ![](media/image35.png)

### Task 4: Load sample data

In this task, you load about 50 products, 5,000 orders and roughly 600 returns. This gives the search, JSONB and scheduling features real data to work with.

1. Run the following commands to load the sample data:

    ```sql
    INSERT INTO retail.products (name, category, price)
    SELECT (ARRAY['Wireless Headphones','Running Shoes','Cotton T-Shirt','Ceramic Mug','Yoga Mat',
                  'Face Serum','Desk Lamp','Bluetooth Speaker','Denim Jacket','Water Bottle'])[1 + (g % 10)]
             || ' Model ' || g,
           (ARRAY['Electronics','Sports','Apparel','Home','Sports',
                  'Beauty','Home','Electronics','Apparel','Sports'])[1 + (g % 10)],
           round((5 + random() * 495)::numeric, 2)
    FROM generate_series(1, 50) g;

    INSERT INTO retail.orders (product_id, customer_id, qty, order_total, ordered_at)
    SELECT p.product_id, s.cust, s.q, round(p.price * s.q, 2),
           now() - ((random() * 90)::int || ' days')::interval
    FROM (SELECT 1 + (random() * 49)::int AS pid,
                 1 + (random() * 999)::int AS cust,
                 1 + (random() * 3)::int  AS q
          FROM generate_series(1, 5000)) s
    JOIN retail.products p ON p.product_id = s.pid;

    INSERT INTO retail.returns (order_id, status, refund_amount, metadata, requested_at)
    SELECT o.order_id,
           (ARRAY['completed','completed','rejected'])[1 + (random() * 2)::int],
           o.order_total,
           jsonb_build_object(
             'reason',  (ARRAY['damaged','wrong_size','not_as_described','changed_mind','late_delivery'])[1 + (random() * 4)::int],
             'channel', (ARRAY['web','mobile','store'])[1 + (random() * 2)::int],
             'photos',  (random() * 3)::int),
           o.ordered_at + interval '5 days'
    FROM retail.orders o
    WHERE random() < 0.12;

    SELECT (SELECT count(*) FROM retail.products) AS products,
           (SELECT count(*) FROM retail.orders)   AS orders,
           (SELECT count(*) FROM retail.returns)  AS returns;
    ```

    ![](media/image36.png)

2. Verify that the result shows 50 products, 5,000 orders and about 600 returns.

    ![](media/image37.png)

## Exercise 2: Fuzzy search, JSONB and a scheduled job

In this exercise, you solve three of CartWise's problems inside the database. You make product search forgive typos, query flexible return data efficiently, and replace the manual nightly refresh with a scheduled job.

### Task 1: Search products with typos by using pg_trgm

Customers mistype product names, and pg_trgm compares strings by their three-letter fragments, so a typo still finds the right product. In this task, you add a trigram index and search for a misspelled word.

1. In the query window that is connected to the **cartwise** database, run the following commands:

    ```sql
    CREATE INDEX idx_products_name_trgm ON retail.products USING gist (name gist_trgm_ops);

    SELECT product_id, name,
           round((1 - ('headphnes' <<-> name))::numeric, 2) AS score
    FROM retail.products
    ORDER BY 'headphnes' <<-> name
    LIMIT 5;
    ```

    ![](media/image38.png)

2. Review the results. The top rows are the Wireless Headphones products, even though the search word is misspelled. The `<<->` operator measures word similarity distance, and the GiST index can serve this kind of nearest-match ordering.

    ![](media/image39.png)

    **Note:** On 50 rows the planner might still scan the table. This is expected. The index matters when the catalog grows.

### Task 2: Query semi-structured return data

Return metadata is stored as JSONB, so each return can carry different attributes without schema changes. In this task, you summarize returns by reason, and then add a GIN index for containment queries.

1. Run the following query to count returns by reason:

    ```sql
    SELECT metadata->>'reason' AS reason, count(*) AS returns, sum(refund_amount) AS refunded
    FROM retail.returns
    GROUP BY 1
    ORDER BY returns DESC;
    ```

    ![](media/image40.png)

2. Add a GIN index, and then use the containment operator to find damaged returns that arrived through the mobile channel:

    ```sql
    CREATE INDEX idx_returns_metadata ON retail.returns USING gin (metadata jsonb_path_ops);

    EXPLAIN (ANALYZE)
    SELECT return_id, refund_amount
    FROM retail.returns
    WHERE metadata @> '{"reason": "damaged", "channel": "mobile"}';
    ```

    **Note:** On a table this small, the planner might still choose a sequential scan. This is expected. The index pays off as the table grows.

    ![](media/image41.png)

### Task 3: Create the refresh procedure

In this task, you create a stored procedure that rebuilds the returns summary table. Putting the refresh in one procedure gives the scheduler a single, repeatable thing to call.

1. Run the following commands to create the procedure, run it once, and check the output:

    ```sql
    CREATE OR REPLACE PROCEDURE retail.refresh_return_stats()
    LANGUAGE sql
    AS $$
      TRUNCATE retail.return_stats;
      INSERT INTO retail.return_stats (category, reason, return_count, refunded)
      SELECT p.category, r.metadata->>'reason', count(*), sum(r.refund_amount)
      FROM retail.returns r
      JOIN retail.orders o   ON o.order_id = r.order_id
      JOIN retail.products p ON p.product_id = o.product_id
      GROUP BY 1, 2;
    $$;

    CALL retail.refresh_return_stats();
    SELECT * FROM retail.return_stats ORDER BY refunded DESC LIMIT 5;
    ```

    ![](media/image42.png)

### Task 4: Schedule the refresh by using pg_cron

pg_cron keeps its job tables in the default postgres database, and it can run a job in another database by using `cron.schedule_in_database`. In this task, you schedule the refresh procedure to run in the cartwise database, and then confirm that the scheduler, not you, ran it.

1. Select the PostgreSQL connection in the Connections section, right-click it, and select Get Started → New Query.

    ![](media/image43.png)

    ![](media/image44.png)

2. In a new query window that is connected to the **postgres** database, run the following commands:

    ```sql
    CREATE EXTENSION IF NOT EXISTS pg_cron;

    SELECT cron.schedule_in_database(
      'refresh-return-stats',
      '* * * * *',
      'CALL retail.refresh_return_stats()',
      'cartwise'
    );

    SELECT jobid, jobname, schedule, database, active FROM cron.job;
    ```

    **Note:** The schedule `* * * * *` runs every minute, which is only for this lab. A production schedule would be nightly, for example `0 2 * * *`. Cron times are in GMT.

    ![](media/image45.png)

    **Troubleshooting:** If you get the error `can only create extension in database postgres` (with a detail about `cron.database_name`), you ran the statements while connected to the cartwise database. pg_cron works only from the postgres database. Run the statements in the **postgres** connection, and then switch back to the **cartwise** connection for the rest of the lab.

3. Wait about two minutes. In the **postgres** connection, run the following query:

    ```sql
    SELECT jobid, status, return_message, start_time, end_time
    FROM cron.job_run_details
    ORDER BY start_time DESC
    LIMIT 5;
    ```

4. Switch back to the **cartwise** connection, and run the following query to confirm that the scheduler refreshed the stats:

    ```sql
    SELECT max(refreshed_at) AS last_refresh, now() - max(refreshed_at) AS age FROM retail.return_stats;
    ```

    The fuzzy search finds headphones, `cron.job_run_details` shows successful runs, and the refresh timestamp is under two minutes old. Leave the job running.

## Exercise 3: Approval rules and events in the database

Business rules that must never be bypassed belong next to the data. In this exercise, you move three rules into HorizonDB: only a requested return can be decided, requests that nobody answers expire, and new requests announce themselves to listening applications.

### Task 1: Create the functions and the trigger

In this task, you create two functions and a trigger. One function enforces the approval rule, one expires stale requests, and the trigger publishes an event for each new request.

1. In the **cartwise** connection, run the following commands:

    ```sql
    CREATE OR REPLACE FUNCTION retail.decide_return(p_return_id int, p_approved boolean, p_approver text)
    RETURNS TABLE (out_return_id int, out_status text)
    LANGUAGE plpgsql
    AS $$
    DECLARE
      v_status text;
    BEGIN
      SELECT r.status INTO v_status
      FROM retail.returns r
      WHERE r.return_id = p_return_id
      FOR UPDATE;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'return % not found', p_return_id;
      END IF;
      IF v_status <> 'requested' THEN
        RAISE EXCEPTION 'return % is already %', p_return_id, v_status;
      END IF;

      UPDATE retail.returns r
      SET status = CASE WHEN p_approved THEN 'approved' ELSE 'rejected' END
      WHERE r.return_id = p_return_id;

      INSERT INTO retail.ops_log (job, detail)
      VALUES ('return-decision',
              format('return=%s approved=%s by=%s', p_return_id, p_approved, p_approver));

      RETURN QUERY SELECT r.return_id, r.status FROM retail.returns r WHERE r.return_id = p_return_id;
    END;
    $$;

    CREATE OR REPLACE FUNCTION retail.expire_stale_returns(p_minutes int)
    RETURNS int
    LANGUAGE plpgsql
    AS $$
    DECLARE
      v_count int;
    BEGIN
      UPDATE retail.returns
      SET status = 'expired'
      WHERE status = 'requested'
        AND requested_at < now() - make_interval(mins => p_minutes);
      GET DIAGNOSTICS v_count = ROW_COUNT;
      IF v_count > 0 THEN
        INSERT INTO retail.ops_log (job, detail)
        VALUES ('expire-stale-returns', v_count || ' returns expired');
      END IF;
      RETURN v_count;
    END;
    $$;

    CREATE OR REPLACE FUNCTION retail.notify_return() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
      PERFORM pg_notify('return_requested', NEW.return_id::text);
      RETURN NEW;
    END;
    $$;

    CREATE TRIGGER trg_return_requested
      AFTER INSERT ON retail.returns
      FOR EACH ROW WHEN (NEW.status = 'requested')
      EXECUTE FUNCTION retail.notify_return();
    ```

    The `FOR UPDATE` row lock means that two managers who decide the same return at the same moment cannot both succeed. The second manager waits, then sees the new status and gets an error.

    ![](media/image46.png)

### Task 2: Test the approval rules in SQL

In this task, you create a high-value return and try to decide it twice. The second attempt should fail, which shows the rule working.

1. Create a return for the highest-value order by running the following command:

    ```sql
    INSERT INTO retail.returns (order_id, refund_amount, metadata)
    SELECT order_id, order_total, '{"reason": "damaged", "channel": "web", "photos": 2}'
    FROM retail.orders
    ORDER BY order_total DESC
    LIMIT 1
    RETURNING return_id, status, refund_amount;
    ```

    ![](media/image47.png)

2. Note the `return_id` in the result we will use this in the next step.

    ![](media/image48.png)

3. In the following commands, replace both instances of `<return-id>` with that value, and then run them:

    ```sql
    SELECT * FROM retail.decide_return(<return-id>, true, 'manager@cartwise.example');

    SELECT * FROM retail.decide_return(<return-id>, false, 'manager@cartwise.example');
    ```

    ![](media/image49.png)

4. The first call returns **approved**. The second call fails with a message that the return is already approved. Check the audit trail by running the following query:

    ```sql
    SELECT * FROM retail.ops_log ORDER BY log_id DESC LIMIT 3;
    ```

    ![](media/image50.png)

### Task 3: Expire unanswered requests

In this task, you create a second return and expire it immediately by using a zero-minute timeout. This proves that unanswered requests no longer stay open forever.

1. Run the following command:

    ```sql
    INSERT INTO retail.returns (order_id, refund_amount, metadata)
    SELECT order_id, order_total, '{"reason": "late_delivery", "channel": "mobile", "photos": 0}'
    FROM retail.orders
    ORDER BY order_total DESC
    OFFSET 1 LIMIT 1
    RETURNING return_id;
    ```

    ![](media/image51.png)

2. Run the following command:

    ```sql
    SELECT retail.expire_stale_returns(0);
    ```

    Confirm that the function returns **1** and that the return now has the status **expired**.

    ![](media/image52.png)

### Task 4: Schedule the expiry by using pg_cron

In this task, you schedule the expiry function so that it runs without anyone starting it. Like the refresh job, it is created from the postgres database and runs in the cartwise database.

1. Switch to the **postgres** connection, and then run the following commands:

    ```sql
    SELECT cron.schedule_in_database(
      'expire-stale-returns',
      '*/5 * * * *',
      'SELECT retail.expire_stale_returns(10)',
      'cartwise'
    );

    SELECT jobid, jobname, schedule, database FROM cron.job ORDER BY jobid;
    ```

    Verify that the job was created by checking the returned job ID. For example, a result of 2 indicates that the job was assigned ID 2.

    ![](media/image53.png)

2. Verify that both scheduled jobs are listed:

    ```sql
    SELECT jobid, jobname, schedule, database
    FROM cron.job
    ORDER BY jobid;
    ```

    The query should list both the existing refresh job and the newly created `expire-stale-returns` job. The new job should show the schedule `*/5 * * * *` and the database `cartwise`.

    ![](media/image54.png)

    Every five minutes, the job checks for returns that have been awaiting a decision for more than 10 minutes and expires eligible returns, according to the function's implementation.

## Exercise 4: A REST API for the returns service

HorizonDB speaks standard PostgreSQL, so your application needs only a normal driver. In this exercise, you build a small REST API with FastAPI and psycopg. The API uses a connection pool, which keeps a few connections open and reuses them across requests.

### Task 1: Install the packages

In this task, you install the web framework, the web server and the PostgreSQL driver with its connection pool. These are the only dependencies the API needs.

1. Open a new terminal.

    ![](media/image55.png)

2. Run the following command to install packages:

    ```powershell
    pip install fastapi "uvicorn[standard]" "psycopg[binary,pool]"
    ```

    ![](media/image56.png)

### Task 2: Set the connection variables

In this task, you store the connection details in environment variables so the API code doesn't contain credentials. The variables last only for the terminal window where you set them.

1. In the terminal that you will use to run the API, run the following commands. Replace `<cluster-host-name>` with the primary endpoint that you saved in Exercise 0:

    ```powershell
    $env:PGHOST="<cluster-host-name>"
    $env:PGUSER="cartwise"
    $env:PGPASSWORD="Password@123!"
    ```

    ![](media/image57.png)

### Task 3: Create the API

In this task, you create the API code. It exposes four endpoints: search products, create a return, decide a return and read a return.

1. Navigate to File explorer, select File-\>New file-\>Python File.

    ![](media/image58.png)

    ![](media/image59.png)

2. In Visual Studio Code, create a new file named **returns_api.py**, and then add the following code:

    ```python
    import os

    import psycopg
    from fastapi import FastAPI, HTTPException
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    from pydantic import BaseModel

    conninfo = (
        f"host={os.environ['PGHOST']} port=5432 dbname=cartwise "
        f"user={os.environ['PGUSER']} password={os.environ['PGPASSWORD']} sslmode=require"
    )
    pool = ConnectionPool(
        conninfo, min_size=1, max_size=5,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )

    app = FastAPI(title="CartWise Returns API")

    class NewReturn(BaseModel):
        order_id: int
        reason: str
        channel: str = "api"

    class Decision(BaseModel):
        approved: bool
        approver: str

    @app.get("/products")
    def search_products(q: str, limit: int = 5):
        sql = """
            SELECT product_id, name, category, price,
                   round((1 - (%s::text <<-> name))::numeric, 2) AS score
            FROM retail.products
            ORDER BY %s::text <<-> name
            LIMIT %s
        """
        with pool.connection() as conn:
            return conn.execute(sql, (q, q, limit)).fetchall()

    @app.post("/returns", status_code=201)
    def create_return(body: NewReturn):
        sql = """
            INSERT INTO retail.returns (order_id, refund_amount, metadata)
            SELECT order_id, order_total,
                   jsonb_build_object('reason', %s::text, 'channel', %s::text)
            FROM retail.orders WHERE order_id = %s
            RETURNING return_id, status, refund_amount
        """
        with pool.connection() as conn:
            row = conn.execute(sql, (body.reason, body.channel, body.order_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="order not found")
        return row

    @app.post("/returns/{return_id}/decision")
    def decide(return_id: int, body: Decision):
        sql = ("SELECT out_return_id AS return_id, out_status AS status "
               "FROM retail.decide_return(%s, %s, %s)")
        try:
            with pool.connection() as conn:
                return conn.execute(sql, (return_id, body.approved, body.approver)).fetchone()
        except psycopg.errors.RaiseException as exc:
            raise HTTPException(status_code=409, detail=exc.diag.message_primary)

    @app.get("/returns/{return_id}")
    def get_return(return_id: int):
        sql = ("SELECT return_id, status, refund_amount, metadata, requested_at "
               "FROM retail.returns WHERE return_id = %s")
        with pool.connection() as conn:
            row = conn.execute(sql, (return_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="return not found")
        return row
    ```

    ![](media/image60.png)

    Notice what the API does not contain: no approval logic. The rules live in `retail.decide_return`, so every client (this API, a batch job or a support tool) gets the same behavior.

    Note: Save this file in Documents.

    ![](media/image61.png)

### Task 4: Start the API and open the test page

In this task, you start the API and open the interactive test page that FastAPI generates. The page lets you call each endpoint from your browser without writing a client.

1. In the terminal where you set the connection variables, go to the folder that contains **returns_api.py**, and then run the following command:

    ```powershell
    +++cd documents+++
    +++python -m uvicorn returns_api:app --port 8000+++
    ```

    ![](media/image62.png)

2. Open a browser and go to `http://127.0.0.1:8000/docs`. FastAPI generates an interactive test page where you can call each endpoint by selecting **Try it out**.

    ![](media/image63.png)

    **Note:** If you open only `http://127.0.0.1:8000` (without `/docs`), the browser shows `{"detail":"Not Found"}`. This is normal and proves that the API is running. The API defines no page at the root address, so add `/docs` to the address.

### Task 5: Call the API

In this task, you call the four endpoints from the test page in the order a real return would travel: search, request, decide and verify. A duplicate decision shows the database rule surfacing as an HTTP error.

#### Search products

1. On the test page at `http://127.0.0.1:8000/docs`, select the blue **GET /products** row to expand it.

    ![](media/image64.png)

2. Select **Try it out** (top right of the expanded row).

    ![](media/image65.png)

3. In the **q** field, enter `headphnes`. Leave **limit** as 5.

    ![](media/image66.png)

4. Select **Execute**, and then scroll down to **Response body**. You should see Wireless Headphones products at the top, even though the word is misspelled.

    ![](media/image67.png)

    ![](media/image68.png)

#### Create a return

1. Expand **POST /returns**, and then select **Try it out**.

    ![](media/image69.png)

2. Replace the request body with the following:

    ```json
    {
      "order_id": 1,
      "reason": "damaged"
    }
    ```

    ![](media/image70.png)

3. Select **Execute**. Note the `return_id` in the response and the status **requested** we will use it in the next step.

    ![](media/image71.png)

    ![](media/image72.png)

#### Approve the return

1. Expand **POST /returns/{return_id}/decision**, and then select **Try it out**.

    ![](media/image73.png)

2. In the path field, enter your `return_id`.

3. Use the following request body:

    ```json
    {
      "approved": true,
      "approver": "manager@cartwise.example"
    }
    ```

    ![](media/image74.png)

4. Select **Execute**. The status should be **approved**.

    ![](media/image75.png)

    ![](media/image76.png)

5. Select **Execute** again. This time you should get a **409** response with a message that the return is already approved.

    ![](media/image77.png)

#### Check the result

1. Expand **GET /returns/{return_id}**, and then select **Try it out**.

    ![](media/image78.png)

2. Enter the same `return_id`, and then select **Execute**. The status should be **approved**.

    ![](media/image79.png)

    ![](media/image80.png)

    **Note:** If any call shows a 500 error, look at the PowerShell window that is running uvicorn. It prints the full error text, which usually points to a missing table or function from Exercises 1 to 3.

### Task 6: Receive events from the database

The trigger from Exercise 3 sends a notification whenever a return is requested. In this task, you write a small listener that receives those notifications, the way a fulfillment or email service would.

1. Open a new terminal, Replace `<cluster-host-name>` with the primary endpoint that you saved in Exercise 0:

    ```powershell
    $env:PGHOST="<cluster-host-name>"
    $env:PGUSER="cartwise"
    $env:PGPASSWORD="Password@123!"
    ```

2. Create a new python file named as **listener.py**, and then add the following code:

    ```python
    import os

    import psycopg

    conn = psycopg.connect(
        host=os.environ["PGHOST"], port=5432, dbname="cartwise",
        user=os.environ["PGUSER"], password=os.environ["PGPASSWORD"],
        sslmode="require", autocommit=True,
    )
    conn.execute("LISTEN return_requested")
    print("Waiting for new return requests (Ctrl+C to stop)...")
    for note in conn.notifies():
        print(f"New return requested: id={note.payload}")
    ```

3. Run the listener:

    ```powershell
    +++cd documents+++
    +++python listener.py+++
    ```

4. With the API still running in another terminal, create a return again by using **POST /returns** on the test page. The listener prints the new return ID within a second. This is how a fulfillment or email service can react to returns without polling the table.

#### Create a return

1. Expand **POST /returns**, and then select **Try it out**.

    ![](media/image69.png)

2. Replace the request body with the following:

    ```json
    {
      "order_id": 1,
      "reason": "damaged"
    }
    ```

    ![](media/image70.png)

3. Select **Execute**.

    ![](media/image71.png)

    ![](media/image72.png)

    The API creates and decides returns, a duplicate decision returns 409, and the listener prints a notification for a new request.

    ![](media/image81.png)

## Summary

In this lab, you modernized the CartWise returns process by moving it from email and manual steps into Azure HorizonDB. You deployed a cluster, attached a parameter group that allows and preloads extensions, and created the cartwise database with a realistic retail data set. You used pg_trgm to make product search forgive typos, queried flexible JSONB return data with a GIN index, and replaced the manual nightly refresh with a pg_cron job that runs in another database. You then enforced the approval rules inside the database with a transactional function, expired unanswered requests on a schedule, and published events with a trigger and pg_notify. Finally, you exposed all of it through a Python REST API that uses a standard driver and a connection pool, and received live events with a listener. CartWise now has one consistent, auditable returns process that every client shares, and the cartwise database is ready for the monitoring work in Lab 8.
