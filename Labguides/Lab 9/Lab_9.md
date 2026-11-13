# Lab 9: Implement High Availability and Failover Recovery in Azure HorizonDB

### Estimate Time: 60 minutes

## Scenario

SchedPro Automotive Components GmbH is a Tier 1 supplier of brake, steering, and transmission components to European automotive manufacturers. The company operates six plants with approximately 1,200 connected machines, including CNC machines, presses, welding cells, and industrial robots.

Programmable logic controllers (PLCs) send production data to the Manufacturing Execution System (MES) every few seconds. The data includes temperature, speed, cycle time, downtime, and quality alerts. The MES uses this information to track work orders and calculate **Overall Equipment Effectiveness (OEE)**, a key measure of manufacturing performance.

### The challenge

Last quarter, the MES database at one of SchedPro's German plants experienced an infrastructure failure during the night shift. The operations team had to promote the standby server manually, and database recovery took 38 minutes. Because the PLC gateways can buffer only about two minutes of readings, much of the production data was lost. Supervisors had to reconcile production counts manually, putting a just-in-time customer delivery at risk.

SchedPro also experiences performance issues during shift changes at 06:00, 14:00, and 22:00. More than 40 supervisors access OEE dashboards simultaneously, generating reporting queries on the same database that processes incoming PLC data. This additional workload increases write latency and affects production monitoring.

### The proposed solution

Anja Brandt, VP of Manufacturing IT, has approved an initial deployment of Azure HorizonDB for the MES databases at two German plants. As the platform engineer, you will provision the HorizonDB cluster, configure high availability and read scaling, deploy the database schema, run production monitoring queries, and test failover behavior. The results will help SchedPro evaluate whether HorizonDB meets its availability, data-access, and performance requirements before expanding the deployment to the remaining plants.

### Objectives

By the end of this lab, you will be able to:
- Deploy Azure HorizonDB with PostgreSQL 17 and configure high availability with a readable replica.
- Create a manufacturing database and load sample production data.
- Execute SQL queries to analyze work orders, production events, downtime, and quality alerts.
- Validate read-only and read/write endpoint behavior.
- Initiate a forced failover and monitor database connectivity during recovery.
- Measure the approximate write interruption and validate recovery against the 120-second target.


## Exercise 1: Provision the SchedPro HorizonDB cluster

In this exercise, you provision an Azure HorizonDB cluster for SchedPro's Manufacturing Execution System (MES). Configure PostgreSQL 17, zone-redundant high availability, and one readable replica. You will use the cluster in later exercises to load production data, run monitoring queries, and test failover behavior.

### Task 1: Open the create wizard

1. Open a web browser and navigate to +++ +++https://portal.azure.com/+++.

1. Sign in to the **Azure portal** using the following credentials:

    Username - +++@lab.CloudPortalCredential(User1).Username+++

    TAP Token - +++@lab.CloudPortalCredential(User1).AccessToken+++

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-01.png)

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-02.png)

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-03.png)

1. In the search box at the top of the page, enter `Azure HorizonDB`. Under **Services**, select **Azure HorizonDB**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-04.png)

1. Select **Create**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-05.png)


### Task 2: Configure the cluster

1. Configure the cluster settings using the values in the following table. Leave any settings not listed at their defaults.

    | **Setting** | **Value** |
    | --- | --- |
    | Subscription | @lab.CloudSubscription.Name |
    | Resource group | @lab.CloudResourceGroup(HorizonDB-RG).Name |
    | Cluster name | `schedpro-mes-@lab.LabInstance.Id` |
    | Region | @lab.CloudResourceGroup(HorizonDB-RG).Location |
    | PostgreSQL version | **17** |
    | vCores | **2** |
    | High availability | **Zone redundant** |
    | Readable HA replicas | **1** |
    | Authentication | **PostgreSQL authentication** |
    | Admin username | +++AdminHorizon+++ |
    | Admin password | +++Password@123!+++ |

    Click **Next.**

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-06.png)

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-07.png)


### Task 3: Configure networking and create the cluster

1. On the **Networking** tab, make sure the connectivity method is **Public access**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-08.png)

1. Under firewall rules, enable **Allow public access from any Azure service within Azure to this cluster**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-09.png)

1. Select **Add current client IP address** to add your current public IP address to the firewall rules.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-10.png)

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-11.png)

1. Select **Review + create**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-12.png)

1. Select **Create**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-13.png)

1. Wait for 10-15 mins to complete the deployment.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-14.png)

1. Click **Go to resource group**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-15.png)

1. Select the newly created **HorizonDB cluster**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-16.png)


### Task 4: Connect to the cluster

1. In the overview, copy the Primary endpoint and save it in Notepad. You will use it to connect to the cluster.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-17.png)

1. Open **Cloud Shell** from the Azure portal toolbar. Select **Bash**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-18.png)

1. Select **No storage account required**, select your subscription, and then select **Apply**. Wait for Azure Cloud Shell to initialize.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-19.png)

1. Run the following command to connect to HorizonDB. Replace `<horizon-endpoint>` with your cluster's primary endpoint

    `psql "host=<horizon-endpoint> port=5432 dbname=postgres user=AdminHorizon sslmode=require"`

    Example:

    `psql "host= schedpro-mes23445.cce37d0f4ffb.centralus.horizondb.azure.com port=5432 dbname=postgres user= AdminHorizon sslmode=require"`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-20.png)

1. Enter the password: Password@123!

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-21.png)

1. Verify that the connection succeeds and the psql prompt appears.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-22.png)


## Exercise 2: Build the MES database

In this exercise, you create the SchedPro MES database, define its schema, load sample production data, and run queries used for factory monitoring. The exercise uses standard PostgreSQL commands to validate database compatibility.

### Task 1: Create the database

Create a dedicated database for SchedPro's MES workload and define connection shortcuts for subsequent tasks.

1. In CloudShell, run the following command to create a database:

    `CREATE DATABASE schedpro;`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-23.png)

1. Reconnect to the newly created database:

    `\c schedpro`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-24.png)


### Task 2: Create the machines table

Create a table to store the factory machines referenced by work orders and production events.

1. In the psql session, run the following command:

    ```
    CREATE TABLE machines (
        machine_id SERIAL PRIMARY KEY,
        plant_code VARCHAR(20) NOT NULL,
        machine_code VARCHAR(30) NOT NULL,
        machine_type VARCHAR(30),
        status VARCHAR(20) DEFAULT 'ACTIVE',
        target_oee NUMERIC(5,2) DEFAULT 85.0
    );
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-25.png)

1. Review the table definition:

    - `SERIAL PRIMARY KEY` generates a unique identifier for each machine.
    - `NOT NULL` requires a value for the plant and machine code.
    - `DEFAULT` supplies a value when status or target OEE is not specified.


1. Verify the table structure:

    `\d machines`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-26.png)


### Task 3: Create the work_orders table

Create a table to track planned and actual production quantities for each work order. A foreign key links each work order to a machine.

1. Run the following command:

    ```
    CREATE TABLE work_orders (
        work_order_id SERIAL PRIMARY KEY,
        machine_id INT REFERENCES machines(machine_id),
        work_order_number VARCHAR(30) NOT NULL,
        part_number VARCHAR(30),
        customer_code VARCHAR(20),
        planned_qty INT,
        actual_qty INT DEFAULT 0,
        status VARCHAR(20),
        shift CHAR(1)
    );
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-27.png)

1. Verify the table structure and inspect its foreign-key constraint:

    `\d work_orders`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-28.png)


### Task 4: Create the production_events table

Create a table for production telemetry collected from PLCs, including sensor readings, downtime events, and quality alerts.

1. Run the following command:

    ```
    CREATE TABLE production_events (
        event_id BIGSERIAL PRIMARY KEY,
        machine_id INT REFERENCES machines(machine_id),
        event_type VARCHAR(30) NOT NULL,
        event_value NUMERIC(12,2),
        plc_id VARCHAR(30),
        recorded_at TIMESTAMPTZ DEFAULT now()
    );
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-29.png)

1. Review the main column definitions:

    - `BIGSERIAL` provides a large auto-incrementing identifier for production events.
    - `NUMERIC(12,2)` stores numeric readings with two decimal places.
    - `TIMESTAMPTZ DEFAULT now()` records the event timestamp when no value is supplied.


1. List the tables in the database:

    `\dt`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-30.png)


### Task 5: Load the sample production data

1. Select **Manage files->Upload** to upload the seed.sql file to Azure Cloud Shell.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-31.png)

1. Navigate to C:\LabFiles\seed.sql and select the file to upload.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-32.png)

1. Enter the following command to exit from psql and return to the Bash prompt:

    `\q`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-33.png)

1. Enter the following command to verify that the file exists in Azure Cloud Shell:

    `ls -lh ~/seed.sql`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-34.png)

1. Run the following command to load the sample data into the schedpro database on Azure HorizonDB:

    `psql "host=<horizon-primary-endpoint> port=5432 dbname=schedpro user=AdminHorizon sslmode=require" -v ON_ERROR_STOP=1 -f ~/seed.sql`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-35.png)

1. Enter the password: Password@123!

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-36.png)

1. You will get the following output:

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-37.png)

1. Connect to the schedpro database by running the following command:

    `psql "host=<horizon-primary-endpoint> port=5432 dbname=schedpro user=AdminHorizon sslmode=require"`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-38.png)

1. Enter password: Password@123!

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-39.png)

1. Verify that the sample data has been loaded by running the following queries:

    ```
    SELECT COUNT(*) AS machines
    FROM machines;

    SELECT COUNT(*) AS work_orders
    FROM work_orders;

    SELECT COUNT(*) AS production_events
    FROM production_events;
    ```

    >[!Note] Confirm that each query returns the expected number of records.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-40.png)


### Task 6: Run production queries

Run representative MES queries to review work-order progress and identify recent downtime and quality alerts.

1. Run the following query to view work orders in progress and their completion percentages:

    ```
    SELECT m.plant_code, m.machine_code, wo.work_order_number, wo.part_number,
           wo.actual_qty, wo.planned_qty,
           ROUND(100.0 * wo.actual_qty / NULLIF(wo.planned_qty,0), 1) AS completion_pct
    FROM machines m
    JOIN work_orders wo ON wo.machine_id = m.machine_id
    WHERE wo.status = 'IN_PROGRESS'
    ORDER BY m.plant_code, m.machine_code;
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-41.png)

1. Review the results to compare actual production quantities with planned quantities.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-42.png)

1. Run the following query to identify downtime and quality alerts recorded during the last hour:

    ```
    SELECT m.machine_code, e.event_type, count(*) AS events
    FROM production_events e
    JOIN machines m USING (machine_id)
    WHERE e.recorded_at > now() - interval '1 hour'
      AND e.event_type IN ('DOWNTIME','QUALITY_ALERT')
    GROUP BY m.machine_code, e.event_type
    ORDER BY events DESC;
    ```

1. Review the output.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-43.png)


## Exercise 3: Route reporting queries to the read-only endpoint

During shift changes, production reports can add database workload while PLC gateways continue recording production events. SchedPro needs to run reporting queries through its read-only endpoint to separate reporting activity from production writes.

In this exercise, you’ll inspect the cluster’s replica configuration, run a production report against the read-only endpoint, and verify that write operations are rejected there but succeed through the primary endpoint.

### Task 1: Inspect the replicas

Review the cluster's replica configuration to identify the endpoints used for production writes and reporting queries.

1. In the Azure portal, open your HorizonDB cluster.

1. Navigate to **Settings** > **Replicas**, to find the replica configuration.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-44.png)

1. Confirm that you see one **ReadWrite** replica and one **Read** replica.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-45.png)

1. Locate the read/write and read-only endpoint hostnames. Copy both values in Notepad for use in the following tasks.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-46.png)


### Task 2: Run the production report on the read-only endpoint

Connect to the read-only endpoint and summarize production events across plants and machine types.

1. In Azure Cloud Shell, select **Bash**. If you are connected to psql, enter `\q` to return to the Bash prompt.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-47.png)

1. Run the following command, replacing `<read-only-endpoint>` with the hostname identified in Task 1:

    `psql "host=<read-only-endpoint> port=5432 dbname=schedpro user=AdminHorizon sslmode=require"`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-48.png)

1. Enter password: Password@123!

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-49.png)

1. Confirm that you are on a replica. `pg_is_in_recovery()` is a standard PostgreSQL function that returns `true` on a replica:

    `SELECT pg_is_in_recovery() AS is_replica, current_database();`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-50.png)

1. Run the following query to summarize production events by plant, machine type, and event type:

    ```
    SELECT m.plant_code, m.machine_type, e.event_type,
           count(*) AS events, round(avg(e.event_value),2) AS avg_value
    FROM production_events e
    JOIN machines m USING (machine_id)
    GROUP BY m.plant_code, m.machine_type, e.event_type
    ORDER BY events DESC
    LIMIT 10;
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-51.png)

1. Review the results to identify the most frequently recorded event categories.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-52.png)


### Task 3: Verify that the read-only endpoint rejects writes

Attempt to insert a production event through the read-only endpoint and confirm that the operation is rejected.

1. In the same psql session, run:

    ```
    INSERT INTO production_events (machine_id, event_type, event_value, plc_id)
    VALUES (1, 'PART_PRODUCED', 1, 'PLC-CNC-101');
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-53.png)

1. Confirm that the operation fails with a read-only transaction or permission error. The exact error message may vary.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-54.png)

1. Leave the session with `\q`.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-55.png)


### Task 4: Verify that writes succeed on the primary

Connect to the primary endpoint and repeat the insert to confirm that the write workload uses the read/write endpoint.

1. At the Cloud Shell Bash prompt, run the following command, replacing `<primary-endpoint>` with the read/write hostname identified in Task 1:

    `psql "host=<primary-endpoint> port=5432 dbname=schedpro user=AdminHorizon sslmode=require"`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-56.png)

1. Enter password: +++Password@123!+++

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-57.png)

1. Run the following statement:

    ```
    SELECT pg_is_in_recovery() AS is_replica;

    INSERT INTO production_events (machine_id, event_type, event_value, plc_id)
    VALUES (1, 'PART_PRODUCED', 1, 'PLC-CNC-101');
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-58.png)

1. Confirm that the insert succeeds.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-59.png)

1. Leave the session with `\q`.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-60.png)


## Exercise 4: Test HorizonDB Failover and Measure Recovery

In this exercise, you will validate SchedPro Automotive Components GmbH's high-availability requirements by initiating a forced failover on Azure HorizonDB while simulating production writes and dashboard reads.

SchedPro's PLC gateways can buffer only 120 seconds of production data. You will monitor database connectivity during failover, measure the approximate interruption to successful writes, and compare the observed recovery time with SchedPro's 120-second target.

You will use two monitoring scripts:
- **PLC gateway monitor:** Inserts a heartbeat event through the read/write endpoint approximately every second.
- **OEE dashboard monitor:** Checks the reader endpoint approximately every second to observe read availability.


You will initiate a forced failover through the Azure portal, observe both monitors, and validate database connectivity and heartbeat records after recovery.

### Task 1: Prepare the monitoring environment

In this task, you will identify the replica endpoints and configure the connection settings used by both monitoring scripts.

1. Open the HorizonDB cluster you created in Exercise 1 in the Azure portal.

1. Under Settings, select **High availability**, then select **Manage replicas and failover**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-61.png)

1. Identify the replicas and record their current roles:

    - The replica with the **ReadWrite** role is the primary endpoint for production writes.
    - The replica with the **Read** role is the reporting endpoint.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-62.png)


1. Copy both endpoint hostnames. Keep the portal open so you can return to it after the failover.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-63.png)

1. Open Azure Cloud Shell and select **Bash**.

1. Set the connection variables. Replace the endpoint placeholders with the hostnames you copied in step 4.

    ```
    export PGHOST_RW="<read-write-endpoint>"
    export PGHOST_RO="<read-only-endpoint>"
    export PGUSER="AdminHorizon"
    export PGDATABASE="schedpro"
    export PGPORT="5432"
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-64.png)

1. Set the password for the current Cloud Shell session:

    ```
    read -s -p "HorizonDB password: " PGPASSWORD
    echo
    export PGPASSWORD
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-65.png)

    When prompted, enter the PostgreSQL administrator password as +++Password@123!+++

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-66.png)

1. Verify that the primary endpoint accepts a connection:

    `psql "host=$PGHOST_RW port=$PGPORT dbname=$PGDATABASE user=$PGUSER sslmode=require connect_timeout=5" -c "SELECT current_database(), pg_is_in_recovery();"`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-67.png)

    Expected result: current_database() returns schedpro and pg_is_in_recovery() returns false.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-68.png)

1. Verify that the read-only endpoint accepts a connection:

    `psql "host=$PGHOST_RO port=$PGPORT dbname=$PGDATABASE user=$PGUSER sslmode=require connect_timeout=5" -c "SELECT current_database(), pg_is_in_recovery();"`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-69.png)

    Expected result: current_database() returns schedpro and pg_is_in_recovery() normally returns true when the reader endpoint connects to a standby replica.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-70.png)

    If either connection fails, verify the endpoint hostname, firewall settings, database name, username, and password before continuing.


### Task 2: Create the monitoring scripts

In this task, you will create a script that repeatedly checks database availability and records the time of successful and failed operations.

1. In Cloud Shell, create a file named `watch.sh`:

    ```
    cat > watch.sh <<'EOF'
    #!/usr/bin/env bash
    set -u

    MODE="${1:-ro}"

    case "$MODE" in
      rw) HOST="$PGHOST_RW" ;;
      ro) HOST="$PGHOST_RO" ;;
      *)
        echo "Usage: ./watch.sh rw|ro"
        exit 1
        ;;
    esac

    CONN="host=$HOST port=$PGPORT dbname=$PGDATABASE user=$PGUSER sslmode=require connect_timeout=2"
    down_since=""

    while true; do
      if [ "$MODE" = "rw" ]; then
        SQL="INSERT INTO production_events
          (machine_id, event_type, event_value, plc_id)
          VALUES (1, 'HEARTBEAT', 1, 'PLC-WATCH')
          RETURNING event_id;"
      else
        SQL="SELECT 'read OK, replica=' || pg_is_in_recovery()::text;"
      fi

      OUT=$(psql "$CONN" -X -w -v ON_ERROR_STOP=1 -tA -c "$SQL" 2>&1)
      RC=$?
      NOW=$(date '+%H:%M:%S')

      if [ "$RC" -eq 0 ]; then
        if [ -n "$down_since" ]; then
          echo "$NOW RECOVERED after approximately $(( $(date +%s) - down_since )) seconds"
          down_since=""
        fi
        echo "$NOW UP - $(echo "$OUT" | head -1)"
      else
        if [ -z "$down_since" ]; then
          down_since=$(date +%s)
          echo "$NOW DOWN - outage detected"
        fi
        echo "$NOW DOWN - $(echo "$OUT" | head -1)"
      fi

      sleep 1
    done
    EOF
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-71.png)

1. Review the script:

    - The rw mode inserts a heartbeat record through the read/write endpoint.
    - The ro mode runs a read-only query through the reader endpoint.
    - Each iteration records a timestamp and the result.
    - When an operation fails and later succeeds, the script reports the approximate observed interruption.
    - The `-w` option prevents psql from repeatedly prompting for a password.


1. Make the script executable using the following command:

    `chmod +x watch.sh`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-72.png)

1. Verify that the file exists:

    `ls -l watch.sh`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-73.png)

1. Run the following command:

    `sed -i 's/connect_timeout=2/connect_timeout=10/' watch.sh`


### Task 3: Start the PLC gateway and dashboard monitors

In this task, you will establish a baseline before initiating the failover.

1. Open a second Azure Cloud Shell Bash session in another browser tab.

1. In the second session, repeat the environment-variable setup from Task 1, using the same endpoint hostnames, username, database name, and password.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-74.png)

1. Create `watch.sh` in the second session by repeating Task 2 and make it executable.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-75.png)

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-76.png)

1. In the first Cloud Shell session, start the PLC gateway monitor:

    `./watch.sh rw`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-77.png)

1. In the second Cloud Shell session, start the OEE dashboard monitor:

    `./watch.sh ro`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-78.png)

1. Observe both outputs for at least 10 seconds.

    Expected result:
    - The PLC gateway monitor displays successful `INSERT` operations.
    - The dashboard monitor displays successful reads and the replica status.
    - Both monitors continue to print timestamped results approximately once per second.

    Output from the PLC gateway monitor:

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-79.png)

    Output from the OEE dashboard monitor:

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-80.png)


1. Leave both monitors running.

    If either monitor reports a connection failure before the failover begins, stop and troubleshoot it before proceeding.


### Task 4: Initiate a forced failover in Azure HorizonDB

In this task, you will simulate an unplanned database interruption while the PLC gateway and OEE dashboard monitoring scripts continue running. You will observe how Azure HorizonDB handles the failover and restores database connectivity.

1. Return to the Azure portal and open the HorizonDB cluster you created in Exercise 1.

1. Under **Settings**, select **High availability**, then select **Manage replicas and failover**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-81.png)

1. Review the current replica roles. Identify the replica assigned the **ReadWrite** role and the replica assigned the **Read** role.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-82.png)

1. Select **Forced failover**.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-83.png)

1. Select **Fail over.**

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-84.png)

1. While the failover is in progress, observe both Cloud Shell sessions. Do not stop the monitoring scripts.

1. Record the results in the following table.

    | **Observation** | **PLC gateway monitor (rw)** | **OEE dashboard monitor (ro)** |
    | --- | --- | --- |
    | Before failover | Successful heartbeat inserts | Successful reads |
    | During failover | Record any connection failures | Record successful reads or interruptions |
    | After failover | Record when successful inserts resume | Record when reads resume, if interrupted |
    | Replica status | Not applicable to the insert output | Record the reported pg_is_in_recovery() value |

    **Window 1 output — PLC gateway monitor (rw):**

    The write monitor may report connection failures during failover and should resume successful inserts when the read/write endpoint becomes available again.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-85.png)

    **Window 2 output — OEE dashboard monitor (ro):**

    The reader endpoint's reported replica status may change after failover. A true result indicates that the current connection is to a standby; a false result indicates that it is connected to a primary.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-86.png)

    >[!Note] The exact interruption duration and number of failed checks depend on the environment. Do not assume that either endpoint will remain continuously available.


### Task 5: Validate committed production data

In this task, you will verify that the database remains accessible after failover and that heartbeat records successfully written by the PLC gateway are present.

1. In both Cloud Shell sessions, press Ctrl+C to stop the monitoring scripts.

1. In either Cloud Shell session, connect through the read/write endpoint:

    `psql "host=$PGHOST_RW port=$PGPORT dbname=$PGDATABASE user=$PGUSER sslmode=require connect_timeout=10"`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-87.png)

1. Run the following query to count the committed heartbeat records:

    ```
    SELECT
    count(*) AS committed_heartbeats
    FROM production_events
    WHERE event_type = 'HEARTBEAT'
    AND plc_id = 'PLC-WATCH';
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-88.png)

1. Confirm that the query completes successfully and returns a count.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-89.png)

    >[!Note] The heartbeat count can include records from previous monitoring runs that used the same PLC-WATCH identifier. Therefore, use the count to confirm that heartbeat records exist, not as an exact measure of the writes completed during this failover test.

1. Verify that the connection reaches the current primary:

    ```
    SELECT
    current_database() AS database_name,
    pg_is_in_recovery() AS is_replica;
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-90.png)

    **Expected result:** database_name is schedpro and is_replica is false.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-91.png)

1. Exit the PostgreSQL session:

    `\q`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-92.png)

1. If the read-only endpoint is accessible, connect to it using the following command:

    `psql "host=$PGHOST_RO port=$PGPORT dbname=$PGDATABASE user=$PGUSER sslmode=require connect_timeout=10"`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-93.png)

1. Run the same recovery-status query. Confirm that pg_is_in_recovery() returns true.

    ```
    SELECT
    current_database() AS database_name,
    pg_is_in_recovery() AS is_replica;
    ```

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-94.png)

    Observe the output. If the reader endpoint connects to a standby, is_replica should be true. If it returns false, the endpoint is currently routing the connection to a primary; record the observed result rather than assuming the endpoint is unavailable.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-95.png)

1. Exit the PostgreSQL session:

    `\q`

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-96.png)


## Exercise 5: Clean up resources

The cluster has multiple replicas and is billed while it runs. When your session ends:

1. In the Azure portal, search for `Resource groups`

1. Select HorizonDB-RG and select the horizon db cluster.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-97.png)

1. Select the **three dots(…)->Delete.**

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-98.png)

1. Enter `delete` and then select Delete to delete the HorizonDB cluster.

    ![Screenshot](https://raw.githubusercontent.com/technofocus-pte/azhorizondbdepth/refs/heads/main/Labguides/Lab%209/media/image-99.png)


## Summary

In this lab, you deployed Azure HorizonDB with PostgreSQL 17, configured zone-redundant high availability with a readable replica, and created the schedpro database to support manufacturing operations. You loaded sample data, executed SQL queries to analyze production activities, and validated read-only and read/write endpoint behavior. Finally, you initiated a forced failover, monitored database connectivity, measured the approximate write interruption, and validated recovery against SchedPro’s 120-second recovery target.
