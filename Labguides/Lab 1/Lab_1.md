# Lab 1: Modernize Northstar Manufacturing’s Operations with Azure HorizonDB

**Estimated duration:** 50 minutes

## Scenario

Northstar Manufacturing Inc., headquartered in Chicago, Illinois, operates production facilities across Illinois, Texas, and Ohio. Its plants rely on CNC machines, hydraulic presses, and industrial robots to meet production schedules and customer delivery commitments. However, equipment details and maintenance requests are scattered across separate operational systems, making it difficult for the IT team to establish a consistent view of equipment status and maintenance activity.

As Northstar prepares to modernize its manufacturing applications and introduce AI-powered capabilities, its first priority is to establish a reliable, centralized database foundation. The company needs a managed PostgreSQL environment that authorized clients can access, where equipment and maintenance data can be stored in related tables and queried together. The environment must also be protected against accidental deletion as development progresses.

As Northstar’s database engineer, you will deploy an Azure HorizonDB cluster, configure client connectivity, and apply a Delete resource lock to protect the cluster. You will then create an operations database, establish relationships between equipment and maintenance records, and perform SQL operations to retrieve and manage the data. By the end of this lab, you will have established the database foundation Northstar needs for its next stage of modernization.

## Objectives

After you complete this lab, you will be able to:

- Describe the core architecture of Azure HorizonDB.

- Deploy an Azure HorizonDB cluster.

- Protect the cluster from accidental deletion with a Delete resource lock.

- Connect to HorizonDB by using psql and verify the session.

- Create a database and two related tables with a foreign key.

- Insert, query, join, update, and delete records by using SQL.

## Exercise 0: Azure HorizonDB at a glance(Read only)

Azure HorizonDB is a fully managed, PostgreSQL-compatible database service on Azure. It is built for demanding transactional workloads and for applications that use AI features directly in the database. You work with it the same way you work with PostgreSQL: with standard clients such as psql, standard SQL, and standard drivers.

| Concept | What it means in this lab |
| --- | --- |
| **Cluster** | The top-level Azure resource you deploy. It has a name, a region, a PostgreSQL version, and a primary endpoint that clients connect to. |
| **Primary endpoint** | The host name your client uses to reach the cluster. |
| **Compute (vCores)** | The processing capacity of the cluster. |
| **High availability** | An optional standby that takes over if the primary fails. |
| **Networking** | Public access with firewall rules controls which clients can connect. |
| **Management plane vs. data plane** | The management plane covers Azure operations such as create, configure, lock, and delete. The data plane covers SQL operations on your data. A resource lock acts on the management plane only. |

## Exercise 1: Deploy an Azure HorizonDB cluster

Northstar developers cannot start building until a managed PostgreSQL environment exists. In this exercise, you create the cluster, set its network access, and copy the endpoint that database clients use to connect.

### Task 1: Open the HorizonDB creation wizard

1. Open a web browser and go to +++https://portal.azure.com/+++.

2. Sign in to the Azure portal with the following credentials:

   - **Username:** +++@lab.CloudPortalCredential(User1).Username+++

   - **TAP Token:** +++@lab.CloudPortalCredential(User1).AccessToken+++

   ![A screenshot of a sign in box AI-generated content may be incorrect.](media/image1.png)

   ![A screenshot of a login screen AI-generated content may be incorrect.](media/image2.png)

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image3.png)

3. In the search box at the top of the page, enter +++Azure HorizonDB+++. Under **Services**, select **Azure HorizonDB**.

   ![](media/image4.png)

4. Select **Create**.

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image5.png)

### Task 2: Configure the cluster

On the **Basics** tab, enter the values in the following table. Leave all other settings at their defaults.

| Setting | Value |
| --- | --- |
| Subscription | Your lab subscription |
| Resource group | ResourceGroup1 |
| Cluster name | northstar-hdb-@lab.LabInstance.Id |
| Region | Central US |
| PostgreSQL version | 17 |
| vCores | 2 |
| High availability | Disabled |
| Authentication | PostgreSQL authentication |
| Admin username | NorthstarAdmin |
| Admin password | Password@123! |

Select **Next**.

![](media/image6.png)

![](media/image7.png)

### Task 3: Configure networking

Your psql client must be allowed to reach the cluster. You do this on the **Networking** tab.

1. Confirm that the connectivity method is **Public access**.

   ![](media/image8.png)

2. Under **Firewall rules**, select **Allow public access from any Azure service within Azure to this cluster**.

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image9.png)

3. Select **Add current client IP address** to add your current public IP address to the firewall rules.

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image10.png)

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image11.png)

### Task 4: Deploy the cluster and copy the endpoint

1. Select **Review + create**, review the summary, and then select **Create**.

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image12.png)

   ![](media/image13.png)

2. Wait for the deployment to finish. This takes about 10 to 15 minutes.

   ![](media/image14.png)

3. When the deployment completes, select **Go to resource group**.

   ![](media/image15.png)

4. Select the new HorizonDB cluster.

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image16.png)

5. On the **Overview** page, copy the **Primary endpoint** and paste it into Notepad. You use it in Exercise 3.

   ![](media/image17.png)

The cluster appears in **ResourceGroup1**, its status shows as available, and you have saved the primary endpoint. The database infrastructure is ready.

## Exercise 2: Protect the cluster against accidental deletion

Deleting a database resource by mistake can disrupt applications and take hours to recover from. Azure resource locks add a safeguard at the management plane so that a cluster cannot be removed by accident. In this exercise, you add a **Delete** lock to the cluster and confirm that it is in place.

> **Important:** A Delete lock protects the Azure resource from management-plane deletion. It does **not** stop SQL statements from changing or deleting records and tables inside the database.

1. On the cluster page, under **Settings** in the left navigation menu, select **Locks**.

   ![](media/image18.png)

2. Select **Add**.

   ![](media/image19.png)

3. Enter the following values:

   | Setting | Value |
   | --- | --- |
   | Lock name | northstar-hdb-delete-lock |
   | Lock type | Delete |
   | Notes | Protect the Northstar HorizonDB cluster from accidental deletion during development. |

   ![](media/image20.png)

4. Select **OK**.

5. Confirm that **northstar-hdb-delete-lock** appears in the list of locks.

![](media/image21.png)

The lock is listed with the type **Delete**.

## Exercise 3: Connect to HorizonDB and inspect the session

With the cluster deployed and protected, you now connect to it as a client would. In this exercise, you use psql in Azure Cloud Shell to open a session and confirm which database and user you are connected as.

1. In the Azure portal toolbar, select **Cloud Shell**, and then select **Bash**.

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image22.png)

2. If prompted, select **No storage account required**, choose your subscription, and then select **Apply**. Wait for Cloud Shell to initialize.

   ![](media/image23.png)

3. Run the following command to connect. Replace &lt;horizon-endpoint> with the primary endpoint you saved in Notepad.

   ```
   psql "host=<horizon-endpoint> port=5432 dbname=postgres user=NorthstarAdmin sslmode=require"
   ```

   For example:

   ```
   psql "host=northstar66681805.c75a9b557f60.centralus.horizondb.azure.com port=5432 dbname=postgres user=NorthstarAdmin sslmode=require"
   ```

   > **Tip:** Do not add spaces after host= or user=. Extra spaces cause the connection to fail.

   ![](media/image24.png)

4. When prompted, enter the password +++Password@123!+++. The password does not appear as you type.

   ![](media/image25.png)

5. Confirm that the connection succeeds and the postgres=> prompt appears.

   ![](media/image26.png)

6. Check the current database and user:

   ```
   SELECT current_database(), current_user;
   ```

   **Expected result:** The query returns postgres and NorthstarAdmin.

![](media/image27.png)

> **Why this matters:** You connect to the default postgres database first because it always exists. In the next exercise you create a dedicated database for Northstar's data instead of storing it in postgres.

## Exercise 4: Create and manage the Northstar operations database

Northstar needs its own database to track equipment and maintenance requests. In this exercise, you create northstar_ops, define two related tables, add sample data, and run the core SQL operations: select, join, update, and delete.

### Task 1: Create the Northstar database

1. Create a dedicated database for the Northstar application:

   ```
   CREATE DATABASE northstar_ops;
   ```

   ![](media/image28.png)

2. Switch to the new database:

   ```
   \c northstar_ops
   ```

   ![](media/image29.png)

3. Verify the active database:

   ```
   SELECT current_database();
   ```

   ![](media/image30.png)

   **Expected result:** The query returns northstar_ops.

   ![](media/image31.png)

### Task 2: Create the equipment table

The equipment table stores one row for each machine. The primary key identifies each machine uniquely, and the other columns record where it is, what type it is, and its current status.

1. Create the table:

   ```
   CREATE TABLE equipment (
       equipment_id SERIAL PRIMARY KEY,
       equipment_name VARCHAR(100) NOT NULL,
       plant_name VARCHAR(100) NOT NULL,
       equipment_type VARCHAR(50) NOT NULL,
       status VARCHAR(30) NOT NULL
   );
   ```

   ![](media/image32.png)

2. Verify that the table exists:

   ```
   \dt
   ```

   **Expected result:** The list shows the equipment table.

   ![](media/image33.png)

### Task 3: Create the maintenance request table

The service_requests table stores maintenance requests. A foreign key links each request to a row in equipment. This link lets an application retrieve a machine and its maintenance history together, and it prevents a request from pointing to equipment that does not exist.

1. Create the table:

   ```
   CREATE TABLE service_requests (
       request_id SERIAL PRIMARY KEY,
       equipment_id INT NOT NULL
           REFERENCES equipment(equipment_id),
       issue_description TEXT NOT NULL,
       priority VARCHAR(20) NOT NULL,
       request_status VARCHAR(30) NOT NULL DEFAULT 'Open',
       created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
   );
   ```

   ![](media/image34.png)

2. Inspect the table definition:

   ```
   \d service_requests
   ```

   ![](media/image35.png)

   **Expected result:** The equipment_id column appears, and a foreign-key constraint references equipment(equipment_id).

   ![](media/image36.png)

### Task 4: Insert equipment and maintenance data

Add sample records that represent Northstar's plants in Illinois, Texas, and Ohio. You query and modify this data in the remaining tasks.

1. Insert the equipment records:

   ```
   INSERT INTO equipment
       (equipment_name, plant_name, equipment_type, status)
   VALUES
       ('CNC Machine 01', 'Chicago Plant, Illinois', 'CNC', 'Operational'),
       ('Hydraulic Press 02', 'Dallas Plant, Texas', 'Press', 'Maintenance'),
       ('Robotic Welder 03', 'Columbus Plant, Ohio', 'Robot', 'Operational');
   ```

   ![](media/image37.png)

2. Insert the maintenance requests:

   ```
   INSERT INTO service_requests
       (equipment_id, issue_description, priority, request_status)
   VALUES
       (1, 'Unusual vibration detected during operation', 'High', 'Open'),
       (2, 'Hydraulic pressure below the expected range', 'Critical', 'In Progress');
   ```

   ![](media/image38.png)

3. Verify the equipment records:

   ```
   SELECT * FROM equipment ORDER BY equipment_id;
   ```

   ![](media/image39.png)

4. Verify the maintenance requests:

   ```
   SELECT * FROM service_requests ORDER BY request_id;
   ```

   ![](media/image40.png)

### Task 5: Join equipment with maintenance requests

Business users rarely want raw tables. They want to know which machine has which problem. A join combines the two tables by using the foreign key.

1. Run the following query:

   ```
   SELECT
       e.equipment_name,
       e.plant_name,
       e.status AS equipment_status,
       s.issue_description,
       s.priority,
       s.request_status
   FROM equipment AS e
   JOIN service_requests AS s
       ON e.equipment_id = s.equipment_id
   ORDER BY s.priority;
   ```

   ![](media/image41.png)

   **Expected result:** Two rows that combine equipment details with the related maintenance request. Rows are sorted alphabetically by priority, so Critical appears before High.

   ![](media/image42.png)

   > **Note:** Robotic Welder 03 does not appear because it has no maintenance request. A standard JOIN returns only rows that match in both tables.

### Task 6: Update a maintenance request

A technician has fixed the vibration problem on the CNC machine. Update the request status, and then query the row to confirm the change was saved.

1. Update the request:

   ```
   UPDATE service_requests
   SET request_status = 'Resolved'
   WHERE request_id = 1;
   ```

   ![](media/image43.png)

2. Verify the update:

   ```
   SELECT
       request_id,
       issue_description,
       request_status
   FROM service_requests
   WHERE request_id = 1;
   ```

   ![](media/image44.png)

   **Expected result:** Request 1 has the status Resolved.

   ![](media/image45.png)

### Task 7: Delete a sample maintenance request

Now practice removing a record. You delete the second sample request and then count the rows that remain.

1. Delete the request:

   ```
   DELETE FROM service_requests
   WHERE request_id = 2;
   ```

   ![](media/image46.png)

2. Verify the remaining request count:

   ```
   SELECT COUNT(*) AS remaining_requests
   FROM service_requests;
   ```

   ![](media/image47.png)

   **Expected result:** remaining_requests is 1.

   *(Screenshot placeholder: count result)*

> **Note:** This statement deletes a row from a table. It does not delete the HorizonDB cluster. The Delete lock you configured in Exercise 2 protects the Azure resource, not individual rows or tables.

![](media/image48.png)

3. Type \\q to exit psql when you finish.

   ![](media/image49.png)

## Exercise 5:Cleanup Resources

### Task 1: Remove the resource lock

A Delete lock blocks deletion until an authorized user removes it. Remove the lock before you try to delete the cluster.

1. Open the HorizonDB cluster in the Azure portal.

2. Select **Settings** > **Locks**.

   ![](media/image50.png)

3. Select **northstar-hdb-delete-lock**, and then select **Delete** to remove the lock.

   ![](media/image51.png)

4. Select Delete.

   ![](media/image52.png)

5. Confirm that the lock no longer appears in the list.

   ![](media/image53.png)

### Task 2: Delete the cluster

Delete the cluster only if you are authorized to do so and the environment is dedicated to this lab.

1. Open the cluster's **Overview** page.

2. Select **Delete**.

   ![](media/image54.png)

3. Review the resource details and then select Delete to permanently delete the Cluster.

   ![](media/image55.png)

## Lab summary

In this lab, you deployed an Azure HorizonDB cluster running PostgreSQL 17 in Central US, protected it with a Delete resource lock, and connected to it by using psql. You then created the northstar_ops database with related equipment and service_requests tables, and used insert, select, join, update, and delete statements to manage the data.

These skills are the foundation for the labs that follow, which cover AI-powered search, vector retrieval, agentic applications, performance optimization, security, and business continuity.
