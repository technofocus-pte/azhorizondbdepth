# Lab 4 — Build a GraphRAG Legal Research Agent on Azure HorizonDB

**Estimate duration: 60 min**

## Lab scenario

Calder & Voss LLP is a law firm that advises employers on complex legal matters. Its associates frequently research questions such as whether a court can narrow an overbroad non-compete agreement instead of striking it down. Answering these questions requires more than finding a single relevant document. Associates must examine related court opinions, trace legal citations, review internal research memos, and consider matter-specific notes to build a complete and well-supported understanding.

In this lab, you build a GraphRAG-based Legal Research Agent using Azure HorizonDB that combines vector search, an Apache AGE citation graph, and relational document storage. You register your own embedding and chat models, create SQL functions for model access, and connect document retrieval with graph-based citation expansion. You then build a Python tool-calling agent that uses these capabilities to retrieve relevant legal evidence, maintain persistent conversation memory, and generate answers grounded in the available research library.

## Learning objectives

After completing this lab, you will be able to:

1. Register AI models and create SQL wrapper functions in HorizonDB.
2. Combine vector search and Apache AGE graph traversal for document retrieval.
3. Build SQL-based GraphRAG retrieval workflows.
4. Develop a Python tool-calling agent with persistent conversation memory.
5. Validate agent responses using retrieved documents and citation relationships.

## Exercise 0: Environment setup

### Task 1: Create the cluster

1. Open a web browser and navigate to +++ https://portal.azure.com/+++.

2. Sign in to the Azure portal using the following credentials:  
   Username - +++@lab.CloudPortalCredential(User1).Username+++  
   TAP Token - +++@lab.CloudPortalCredential(User1).AccessToken+++

   ![](./media/image1.png)

   ![](./media/image2.png)

   ![](./media/image3.png)

3. In the search box at the top of the page, enter +++Azure HorizonDB+++. Under Services, select **Azure HorizonDB**.

   ![](./media/image4.png)

4. Select **Create**.

   ![](./media/image5.png)

5. Use these values and leave everything else at its default.

   | **Setting**            | **Value**                          |
   |------------------------|------------------------------------|
   | Resource group         | ResourceGroup1                     |
   | Cluster name           | legalai-hdb-lab@lab.LabInstance.Id |
   | Region                 | Central US                         |
   | PostgreSQL version     | 17                                 |
   | Compute                | Select Configure -> 4 vCores       |
   | High availability      | Disabled                           |
   | Authentication         | PostgreSQL authentication          |
   | Administrator username | lawadmin                           |
   | Password               | Pass@1234                          |

   ![](./media/image6.png)

   ![](./media/image7.png)

   ![](./media/image8.png)

   ![](./media/image9.png)

6. On the **Networking** tab, make sure the connectivity method is **Public access**.

   ![](./media/image10.png)

7. Under firewall rules, enable **Allow public access from any Azure service within Azure to this cluster**.

   ![](./media/image11.png)

8. Select **Add current client IP address** to add your current public IP address to the firewall rules. Select **Review + create**.

   ![](./media/image12.png)

9. Select **Create** and wait 10 to 15 minutes to complete the deployment.

   ![](./media/image13.png)

10. Select **Go to resource group** -> **HorizonDB cluster** and copy the **Cluster endpoint**.

    ![](./media/image14.png)

    ![](./media/image15.png)

    ![](./media/image16.png)

### Task 2: Prepare your own models (bring your own model)

1. In the Azure portal, open **Microsoft Foundry**.

   ![](./media/image17.png)

2. From the left navigation expand **All models, agents and tools**->select **Microsoft Foundry**.

   ![](./media/image18.png)

3. Select **Create**.

   ![](./media/image19.png)

4. Enter the following details to create a Foundry project:

   | Setting              | Suggested value             |
   |----------------------|-----------------------------|
   | Resource Group       | ResourceGroup1              |
   | Name                 | Foundry @lab.LabInstance.Id |
   | Region               | East US                     |
   | Default Project Name | project@lab.LabInstance.Id  |

   Select **Review+create**.

   ![](./media/image20.png)

   ![](./media/image21.png)

5. Select **Create**.

   ![](./media/image22.png)

6. Select **Go to resource**.

   ![](./media/image23.png)

7. Select **Go to Foundry portal**.

   ![](./media/image24.png)

8. In the Use model section select **view deployments**.

   ![](./media/image25.png)

9. Select **Deploy a base model**.

   ![](./media/image26.png)

10. Search +++text-embedding+++ in the search bar. Then select **text-embedding-3-small** model.

    ![](./media/image27.png)

11. Select Deploy->Custom settings.

    ![](./media/image28.png)

12. Increase Tokens per minute rate limit to 3.17M. Now select **Deploy.**

    ![](./media/image29.png)

13. Save the value of Endpoint and key in the notepad you will use them in the upcoming tasks.

    ![](./media/image30.png)

14. Now deploy chat model. Select **Deploy a base model.**

    ![](./media/image31.png)

15. So search for +++gpt-5.1+++ in the search bar and then select gpt-5.1 model from the search result.

    ![](./media/image32.png)

16. Select Deploy ->Custom settings

    ![](./media/image33.png)

17. Increase Tokens per minute rate limit to **15.29M**. Select **Deploy**

    ![](./media/image34.png)

18. Save the Endpoint and key values in the notepad we will use them in the upcoming task.

    ![](./media/image35.png)

### Task 3: Create and attach the parameter group

This task creates a parameter group that enables the extensions the lab needs, then attaches it to the cluster. It sets only two parameters, and every other setting keeps its default.

Use Azure Cloud Shell (Bash) or any terminal with the Azure CLI installed.

1. Open **Cloud Shell** from the Azure portal toolbar. Select **Bash**.

   ![](./media/image36.png)

2. Select **No storage account required**, select your subscription, and then select **Apply**. Wait for Azure Cloud Shell to initialize.

   ![](./media/image37.png)

3. Run the following command to login into azure:

   ```bash
   +++az login+++
   ```

   ![](./media/image38.png)

   ![](./media/image39.png)

   ![](./media/image40.png)

   ![](./media/image41.png)

   ![](./media/image42.png)

4. Enter +++1+++ and press enter.

   ![](./media/image43.png)

5. Set the names you will use in the following commands. Replace the cluster name if yours is different.

   ```bash
   RG="ResourceGroup1"
   CLUSTER="legalai-hdb-lab@lab.LabInstance.Id"
   PG="legalai-pg"
   ```

   ![](./media/image44.png)

6. Create the parameter group.

   ```bash
   az horizondb parameter-group create \
     --name $PG \
     --resource-group $RG \
     --location centralus \
     --version 17 \
     --parameters "azure.extensions=age,azure_ai,pg_diskann,vector" "shared_preload_libraries=age" \
     --apply-immediately true \
     --description "Lab 4 AGE and vector settings"
   ```

   ![](./media/image45.png)

7. Enter+++y+++

   ![](./media/image46.png)

8. Check that the group was created.

   ```bash
   az horizondb parameter-group show --name $PG --resource-group $RG
   ```

   ![](./media/image47.png)

   ![](./media/image48.png)

9. Attach the parameter group to the cluster. The cluster restarts automatically, which can take several minutes.

   ```bash
   SUB=$(az account show --query id -o tsv)

   az horizondb update \
     --name $CLUSTER \
     --resource-group $RG \
     --parameter-group "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.HorizonDb/parameterGroups/$PG"
   ```

   ![](./media/image49.png)

   ![](./media/image50.png)

10. Confirm the cluster is connected to the group.

    ```bash
    az horizondb parameter-group list-connections --name $PG --resource-group $RG
    ```

    ![](./media/image51.png)

    Your cluster name should appear in the output.

    ![](./media/image52.png)

11. After the restart finishes, connect with psql. Replace `<CLUSTER_ENDPOINT>` with the cluster endpoint from the portal and enter the administrator password when prompted.

    ```bash
    psql "host=<CLUSTER_ENDPOINT> port=5432 dbname=postgres user=lawadmin sslmode=require"
    ```

    ![](./media/image53.png)

12. Enter password as +++Pass@1234+++.

    ![](./media/image54.png)

    ![](./media/image55.png)

13. Run these queries:

    ```sql
    SHOW azure.extensions;
    SHOW shared_preload_libraries;
    ```

    ![](./media/image56.png)

    **Expected result:** azure.extensions shows age,azure_ai,pg_diskann,vector, and shared_preload_libraries includes age.

    ![](./media/image57.png)

### Task 4: Create the lab database and extensions

1. Connect to the postgres database with Visual Studio Code (host = cluster endpoint, port 5432, user lawadmin, SSL mode Require) and run:

   ```sql
   CREATE DATABASE legalai_lab;
   ```

   ![](./media/image58.png)

2. Enter +++\q+++ to terminate the connection:

   ![](./media/image59.png)

3. Open Visual Studio code and navigate to PostgreSQL extension.

   > Note: If the PostgresSQL extension is not available in the VS code go to extensions->search for PostgresSQL->select install.

   ![](./media/image60.png)

4. Select **+Add connection**.

   ![](./media/image61.png)

5. Enter the following connection details:

   | Setting      | Suggested value                                              |
   |--------------|--------------------------------------------------------------|
   | Server name  | Primary endpoint of the cluster which we saved in Exercise 0 |
   | Username     | lawadmin                                                     |
   | Password     | Pass@1234                                                    |
   | Database     | legalai_lab                                                  |
   | Server Group | Servers                                                      |

   ![](./media/image62.png)

6. Select **Test connection** to check the connection.

   ![](./media/image63.png)

7. After running Test connection successfully select **Save & Connect**.

   ![](./media/image64.png)

8. Select **New Query**.

   ![](./media/image65.png)

9. Enter the following query to create new extensions and then select Play button to run the query:

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS pg_diskann CASCADE;
   CREATE EXTENSION IF NOT EXISTS azure_ai;
   CREATE EXTENSION IF NOT EXISTS age CASCADE;

   SELECT extname, extversion
   FROM pg_extension
   WHERE extname IN ('vector', 'pg_diskann', 'azure_ai', 'age')
   ORDER BY extname;
   ```

   ![](./media/image66.png)

   **Expected result:** all four extensions are listed.

   ![](./media/image67.png)

## Exercise 1: Load the research library and build the citation graph

### Task 1: Register your models and wrap them in SQL functions

The application never calls the model functions directly. First, you register your own models in the database, then you create two small wrappers. In Lab 7 you lock these wrappers down so users cannot call the models themselves, and if you change models later you only change them here.

1. To Register the embedding model, replace the placeholders with the values recorded during Exercise 0, Task 2. Use NULL for the API version to use the latest supported version.

   ```sql
   SELECT model_registry.model_add(
       'my-embedding',                              -- model alias
       'https://<your-foundry-resource>.services.ai.azure.com/', -- endpoint URL
       'text-embedding-3-small',               -- deployment name
       'text-embedding-3-small',                    -- model name
       NULL,                                        -- API version
       'subscription-key',                          -- authentication type
       '<your-api-key>'                             -- API key
   );
   ```

   ![](./media/image68.png)

2. Similarly Register the chat model

   ```sql
   SELECT model_registry.model_add(
       'my-chat',                                   -- model alias
       'https://<your-foundry-resource>.services.ai.azure.com/', -- endpoint URL
       'gpt-5.1',                     -- deployment name
       'gpt-5.1',                                   -- model name
       NULL,                                        -- API version
       'subscription-key',                          -- authentication type
       '<your-api-key>'                             -- API key
   );
   ```

   ![](./media/image69.png)

3. Run the following query to verify model registration

   ```sql
   SELECT *
   FROM model_registry.model_list_all();
   ```

   Expected result: Both my-embedding and my-chat appear in the model registry, with their corresponding deployment names and model information.

   ![](./media/image70.png)

4. Create the legal schema and the two wrapper functions. These functions provide a consistent interface for the application, regardless of which registered models are used.

   ```sql
   CREATE SCHEMA IF NOT EXISTS legal;

   CREATE OR REPLACE FUNCTION legal.embed(p_text text)
   RETURNS vector
   LANGUAGE sql STABLE
   AS $$
       SELECT azure_openai.create_embeddings(
           'my-embedding',
           p_text
       )::vector
   $$;

   CREATE OR REPLACE FUNCTION legal.llm(
       p_prompt text,
       p_system text
   )
   RETURNS text
   LANGUAGE sql
   AS $$
       SELECT azure_ai.generate(
           prompt => p_prompt,
           system_prompt => p_system,
           model => 'my-chat'
       )::text
   $$;
   ```

   ![](./media/image71.png)

5. Run the following queries to test both functions.

   **Query 1:**

   ```sql
   SELECT vector_dims(legal.embed('test'));
   ```

   ![](./media/image72.png)

   **Query 2:**

   ```sql
   SELECT legal.llm(
       'Reply with exactly: HorizonDB AI test successful',
       'You are a validation assistant.'
   );
   ```

   ![](./media/image73.png)

### Task 2: Create and load the document table

The library has three kinds of documents: published court opinions, firm research memos and privileged matter notes.

```sql
CREATE TABLE legal.documents (
    doc_id         text PRIMARY KEY,
    title          text NOT NULL,
    doc_type       text NOT NULL CHECK (doc_type IN ('OPINION','MEMO','MATTER_NOTE')),
    decision_year  int  NOT NULL,
    classification text NOT NULL CHECK (classification IN ('PUBLIC','INTERNAL','PRIVILEGED')),
    content        text NOT NULL,
    embedding      vector(1536)
);

INSERT INTO legal.documents (doc_id, title, doc_type, decision_year, classification, content) VALUES
('CASE-001','Alder v. Northgate Freight','OPINION',2009,'PUBLIC','The court held that a non-compete clause is enforceable only if it is no broader than needed to protect a legitimate business interest. It set a three-part reasonableness test covering duration, geographic area and the scope of restricted activity.'),
('CASE-002','Brightwater Logistics v. Harlan','OPINION',2014,'PUBLIC','Following Alder, the court found a two-year nationwide non-compete overbroad but chose to narrow it to one year and the employee home region instead of striking it down. The court said narrowing is appropriate when the employer acted in good faith.'),
('CASE-003','Castellan Medical v. Ortiz','OPINION',2017,'PUBLIC','The court held that a non-compete given by the seller of a business is judged more leniently than one imposed on an employee, because the buyer pays for goodwill. It distinguished Alder on that basis and upheld a five-year restriction.'),
('CASE-004','Dunmore v. Hale Software','OPINION',2019,'PUBLIC','The court held that a trade secret claim fails unless the owner took reasonable steps to keep the information secret. Relying on Brightwater, it refused to use a non-compete to protect information that the employer never treated as confidential.'),
('CASE-005','Evergreen Staffing v. Pruitt','OPINION',2021,'PUBLIC','The court held that paid garden leave can justify a longer restriction because the employee keeps receiving salary. It applied Brightwater on narrowing and Castellan on the weight given to bargained-for consideration.'),
('CASE-006','Fairmont Analytics v. Kessler','OPINION',2023,'PUBLIC','The court decided which state law governs the non-compete of a fully remote employee and applied the law of the state where the employee actually works. It followed Evergreen on garden leave and distinguished Dunmore on the secrecy requirement.'),
('MEMO-001','Memo: Enforceability of Non-Competes After Fairmont','MEMO',2024,'INTERNAL','Associate summary of the current state of non-compete law. After Fairmont, the place where the employee works drives the choice of law, so employers with remote staff should review the governing law in every contract.'),
('MEMO-002','Memo: Narrowing Overbroad Restrictions','MEMO',2022,'INTERNAL','Internal analysis of how courts narrow restrictions under Brightwater and Castellan. We recommend drafting with a fallback structure so that a court has a reasonable narrower clause to enforce.'),
('MEMO-003','Memo: Trade Secret Protection Checklist','MEMO',2020,'INTERNAL','Checklist for employer clients based on Dunmore: restrict access, label confidential material, use exit interviews and keep records of the secrecy measures taken.'),
('NOTE-001','Matter Note: Redwood Systems, Departing Executive','MATTER_NOTE',2024,'PRIVILEGED','Privileged advice to Redwood Systems about enforcing an eighteen-month non-compete against a departing vice president. We rate the risk that a court narrows the clause as high, based on Brightwater and Fairmont, and recommend offering paid garden leave.'),
('NOTE-002','Matter Note: Tidewater Health, Sale of Practice','MATTER_NOTE',2023,'PRIVILEGED','Privileged negotiation notes for the sale of a medical practice. The seller will accept a five-year restriction because Castellan supports it, and our fallback position is three years.'),
('NOTE-003','Matter Note: Nimbus Retail, Remote Hires','MATTER_NOTE',2024,'PRIVILEGED','Privileged advice to Nimbus Retail on the law that governs non-competes for remote employees in several states. We advise using the law of each employee work location, following Fairmont, and updating all new contracts.');
```

**Expected result:** 12 rows inserted.

![](./media/image74.png)

### Task 3: Generate embeddings

This step calls your embedding model once for each document.

```sql
UPDATE legal.documents
SET embedding = legal.embed(title || '. ' || content)
WHERE embedding IS NULL;

SELECT COUNT(*) AS total_docs, COUNT(embedding) AS docs_with_embeddings
FROM legal.documents;
```

**Expected result:** 12 and 12. If the counts differ, check Task 1 and your model registration before you continue.

![](./media/image75.png)

### Task 4: Build the citation graph

The graph holds only document IDs and CITES edges (an edge from A to B means A cites B). The relational table stays the source of truth for the text. Run the CREATE statement once, because a second run creates duplicates.

```sql
SET search_path = ag_catalog, "$user", public;

SELECT create_graph('legal_graph');

SELECT * FROM cypher('legal_graph', $$
    CREATE
      (c1:Document {doc_id: 'CASE-001'}), (c2:Document {doc_id: 'CASE-002'}),
      (c3:Document {doc_id: 'CASE-003'}), (c4:Document {doc_id: 'CASE-004'}),
      (c5:Document {doc_id: 'CASE-005'}), (c6:Document {doc_id: 'CASE-006'}),
      (m1:Document {doc_id: 'MEMO-001'}), (m2:Document {doc_id: 'MEMO-002'}),
      (m3:Document {doc_id: 'MEMO-003'}),
      (n1:Document {doc_id: 'NOTE-001'}), (n2:Document {doc_id: 'NOTE-002'}),
      (n3:Document {doc_id: 'NOTE-003'}),

      (c2)-[:CITES]->(c1),
      (c3)-[:CITES]->(c1),
      (c4)-[:CITES]->(c2),
      (c5)-[:CITES]->(c2), (c5)-[:CITES]->(c3),
      (c6)-[:CITES]->(c5), (c6)-[:CITES]->(c4),

      (m1)-[:CITES]->(c6), (m1)-[:CITES]->(c5), (m1)-[:CITES]->(c1),
      (m2)-[:CITES]->(c2), (m2)-[:CITES]->(c3),
      (m3)-[:CITES]->(c4),

      (n1)-[:CITES]->(m1), (n1)-[:CITES]->(c2), (n1)-[:CITES]->(c6),
      (n2)-[:CITES]->(c3), (n2)-[:CITES]->(m2),
      (n3)-[:CITES]->(c6), (n3)-[:CITES]->(m1)
    RETURN c1
$$) AS (result agtype);
```

![](./media/image76.png)

Verify the graph:

```sql
SELECT * FROM cypher('legal_graph', $$ MATCH (n) RETURN count(n) $$) AS (vertices agtype);

SELECT * FROM cypher('legal_graph', $$ MATCH ()-[r]->() RETURN count(r) $$) AS (edges agtype);
```

**Expected result:** 12 vertices and 20 edges.

![](./media/image77.png)

![](./media/image78.png)

> **Note:** Every cypher() call needs an AS (...) clause with one agtype column for each returned value. If a statement fails with a cypher function error, check that age is preloaded (Exercise 0, Task 2).
>
> **Checkpoint:** You have 12 embedded documents and a graph that records which document cites which.

## Exercise 2: Retrieve with vectors, then expand with the graph

### Task 1: Vector search alone

```sql
SELECT doc_id, title,
       ROUND((embedding <=> legal.embed('Can a court narrow an overbroad non-compete instead of striking it down?'))::numeric, 4) AS distance
FROM legal.documents
ORDER BY distance
LIMIT 3;
```

**Expected result:** CASE-002 (Brightwater Logistics v. Harlan) is first or near the top. The case it builds on, CASE-001, and the later cases that apply it may rank lower or not appear, even though a complete answer needs them. This is the gap the graph fills.

![](./media/image79.png)

### Task 2: Create the graph lookup functions

The first function runs the openCypher queries. AGE needs a literal query string, so the function builds the full statement with format() and runs it with EXECUTE. It checks the ID format first. It returns documents that the starting document cites and documents that cite it.

```sql
CREATE OR REPLACE FUNCTION legal.graph_neighbors(p_doc_id text)
RETURNS TABLE (doc_id text, relation text)
LANGUAGE plpgsql
SET search_path = ag_catalog, legal, public
AS $fn$
BEGIN
    IF p_doc_id !~ '^(CASE|MEMO|NOTE)-[0-9]{3}$' THEN
        RAISE EXCEPTION 'Invalid document id: %', p_doc_id;
    END IF;
    RETURN QUERY EXECUTE format($q$
        SELECT trim(both '"' FROM g.nid::text), trim(both '"' FROM g.rel::text)
        FROM ag_catalog.cypher('legal_graph', $c$
            MATCH (a:Document {doc_id: %1$L})-[:CITES]->(b:Document)
            RETURN b.doc_id, 'cites'
        $c$) AS g(nid ag_catalog.agtype, rel ag_catalog.agtype)
        UNION ALL
        SELECT trim(both '"' FROM g.nid::text), trim(both '"' FROM g.rel::text)
        FROM ag_catalog.cypher('legal_graph', $c$
            MATCH (b:Document)-[:CITES]->(a:Document {doc_id: %1$L})
            RETURN b.doc_id, 'cited_by'
        $c$) AS g(nid ag_catalog.agtype, rel ag_catalog.agtype)
    $q$, p_doc_id);
END;
$fn$;
```

![](./media/image80.png)

The second function adds titles from the relational table. It lists the documents that the starting document cites first (the authority it rests on), then the documents that cite it:

```sql
CREATE OR REPLACE FUNCTION legal.related_docs(p_doc_id text, p_limit int DEFAULT 4)
RETURNS TABLE (doc_id text, title text, relation text)
LANGUAGE sql STABLE
AS $$
    SELECT d.doc_id, d.title, n.relation
    FROM legal.graph_neighbors(p_doc_id) AS n
    JOIN legal.documents AS d ON d.doc_id = n.doc_id
    ORDER BY (n.relation = 'cites') DESC, d.doc_id
    LIMIT p_limit;
$$;
```

![](./media/image81.png)

### Task 3: Test the graph expansion

```sql
SELECT * FROM legal.related_docs('CASE-002', 4);
```

**Expected result:** CASE-001 (cites), then CASE-004, CASE-005 and MEMO-002 (cited_by). A fifth neighbor, NOTE-001, is cut by the limit of 4. Brightwater rests on Alder and was applied by later cases and memos, and the graph shows that in one query.

![](./media/image82.png)

### Task 4: Combine both steps in one function

The vector hit is the starting point, and the graph supplies the connected authority. No document ID is typed by hand.

```sql
CREATE OR REPLACE FUNCTION legal.graphrag_retrieve(p_question text, p_expand int DEFAULT 3)
RETURNS TABLE (doc_id text, title text, found_by text, detail text)
LANGUAGE sql STABLE
AS $$
    WITH q AS (SELECT legal.embed(p_question) AS v),
    seed AS (
        SELECT d.doc_id, d.title, ROUND((d.embedding <=> q.v)::numeric, 4) AS dist
        FROM legal.documents AS d, q
        ORDER BY d.embedding <=> q.v
        LIMIT 1
    )
    SELECT s.doc_id, s.title, 'vector'::text, 'distance ' || s.dist::text FROM seed AS s
    UNION ALL
    SELECT r.doc_id, r.title, 'graph'::text,
           CASE r.relation WHEN 'cites' THEN 'cited by the top result'
                           ELSE 'cites the top result' END
    FROM seed AS s CROSS JOIN LATERAL legal.related_docs(s.doc_id, p_expand) AS r;
$$;

SELECT * FROM legal.graphrag_retrieve('Can a court narrow an overbroad non-compete instead of striking it down?');
```

**Expected result:** CASE-002 found by vector, then CASE-001, CASE-004 and CASE-005 found by graph. The text of the case, the authority it rests on, and the cases that applied it are now available as evidence.

![](./media/image83.png)

> **Checkpoint:** You have a SQL-only GraphRAG retrieval flow. Next, an agent chooses these steps for itself.

## Exercise 3: Build the legal research agent (20 minutes)

The agent has four tools. The model picks one at a time by replying with a small JSON message, the Python program runs the tool against HorizonDB, and the result goes back to the model. The model calls go through legal.llm from Exercise 1, which uses the bring-your-own chat model you registered. The Python program never holds a model key. It only needs the database connection.

| **Tool**               | **What it does**                                                |
|------------------------|-----------------------------------------------------------------|
| search_documents       | Vector search: the 3 closest documents                          |
| find_related_documents | Citation graph expansion from one document (legal.related_docs) |
| get_document           | Full text of one document                                       |
| recall_memory          | Recent messages from this session                               |

The model never receives SQL access. It can only name one of these four tools.

### Task 1: Create the memory table

```sql
CREATE TABLE legal.agent_messages (
    message_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id text NOT NULL,
    db_user    text NOT NULL DEFAULT session_user,
    role       text NOT NULL CHECK (role IN ('user','assistant','tool')),
    content    text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_agent_messages_session ON legal.agent_messages (session_id, message_id);
```

User questions, agent answers and every tool result are stored. This gives you a conversation memory and an audit trail.

![](./media/image84.png)

### Task 2: Open agent.py

1. Navigate to C:\Labfiles and open agent.py in your VS code.

2. Select 3-dots(…) from the top left navigation bar and then select Terminal->New terminal.

   ![](./media/image85.png)

3. Execute the following commands one by one in the terminal:

   ```powershell
   python3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install "psycopg[binary]"
   ```

   ![](./media/image86.png)

4. Then set the connection details. Replace the placeholders with your values which we save in Exercise 0.

   ```powershell
   $env:HORIZONDB_DSN = 'host=<CLUSTER_ENDPOINT> port=5432 dbname=legalai_lab user=lawadmin password=Pass@1234 sslmode=require'
   $env:AGENT_SESSION_ID = 'lab4-demo'
   ```

   ![](./media/image87.png)

### Task 3: Explore how the Legal Research Agent works

The supplied agent.py file contains the complete implementation of the Legal Research Agent. Review the following five code sections to understand how the agent works before running it.

1. The following code configures the Legal Research Agent and defines its available tools.

   ```python
   DSN = os.environ["HORIZONDB_DSN"]
   SESSION_ID = os.getenv(
       "AGENT_SESSION_ID",
       "session-" + uuid.uuid4().hex[:8])
   MAX_STEPS = 5
   DEBUG = False
   ```

   The agent reads its HorizonDB connection details, assigns a session ID to each conversation, and limits the number of tool-execution steps. The TOOL_CATALOG defines the four tools available to the agent: search_documents, find_related_documents, get_document, and recall_memory.

   ![](./media/image88.png)

2. The following code enables GraphRAG-based legal document retrieval.

   ```python
   SEARCH_SQL = """WITH q AS (
       SELECT legal.embed(%s::text) AS v
   )
   SELECT
       d.doc_id,
       d.title,
       d.doc_type,
       ROUND((d.embedding <=> q.v)::numeric, 4),
       LEFT(d.content, 160)
   FROM legal.documents AS d, q
   ORDER BY d.embedding <=> q.v
   LIMIT 3"""
   ```

   This query converts the user's question into an embedding and finds the three most relevant legal documents using vector similarity.

   The agent also uses legal.related_docs() to follow citation relationships between documents and tool_get_document() to retrieve their complete content. Together, these capabilities combine vector search and graph-based retrieval to provide relevant legal context.

   ![](./media/image89.png)

3. The following code defines how the agent interacts with the model.

   ```python
   def ask_model(conn, prompt):
       result = conn.execute(
           """
           SELECT legal.llm(%s::text, %s::text)
           """,
           (prompt, SYSTEM_PROMPT)
       ).fetchone()

       if result is None or result[0] is None:
           raise ValueError(
               "legal.llm returned an empty response."
           )

       return result[0]
   ```

   The system prompt provides the model with instructions about its role, available tools, and response requirements. The model receives the user's request and determines whether to call a tool or return a final answer. The agent parses the model's JSON response and executes the requested action.

   ![](./media/image90.png)

4. The following code connects the tools and manages their execution.

   ```python
   TOOLS = {
       "search_documents": tool_search_documents,
       "find_related_documents": tool_find_related,
       "get_document": tool_get_document,
       "recall_memory": tool_recall_memory,
   }
   ```

   This mapping connects each tool name to its corresponding Python function. When the model requests a tool, the agent uses this mapping to execute the appropriate function, retrieve the result, and send it back to the model.

   ![](./media/image91.png)

5. The following code stores conversation history for persistent memory.

   ```python
   def log(conn, role, content):
       with conn.cursor() as cur:
           cur.execute(
               """
               INSERT INTO legal.agent_messages
                   (session_id, role, content)
               VALUES (%s, %s, %s)
               """,
               (SESSION_ID, role, content)
           )
   ```

   This function stores user and assistant messages in the legal.agent_messages table, associated with the current session ID. The recall_memory tool retrieves recent messages from this table, allowing the agent to use previous conversation context even after it is restarted with the same session ID.

   ![](./media/image92.png)

### Task 4: Run the agent

Run +++python agent.py+++ and ask these questions one at a time. Watch the [step] lines, because they show which tool the model chose.

| **Test** | **Question** | **What You Should See** |
|----------|--------------|-------------------------|
| 1 | Can a court narrow an overbroad non-compete instead of striking it down? | search_documents followed by find_related_documents for CASE-002. The answer cites CASE-002, CASE-001, and supporting documents such as MEMO-002. |
| 2 | What is the reasonableness test for non-competes, and which later documents rely on it? | CASE-001 and its three elements: duration, geographic area, and scope of activity. Related documents: CASE-002, CASE-003, and MEMO-001. |
| 3 | What did I ask you first in this session? | recall_memory retrieves the conversation history and identifies the first question asked in the session. |
| 4 | Is a non-compete in the sale of a business treated differently from one in employment? | CASE-003 explains the more lenient treatment of sale-of-business restrictions and the five-year restriction upheld. |
| 5 | What is the law on cryptocurrency taxation? | The agent states that the research library does not contain relevant information and does not invent an answer. |

Note: The wording of answers varies between runs, and it also depends on the chat model you deployed. Judge the tools used, the documents retrieved and the citations, not the exact sentences. If the model replies with text that is not JSON, the program asks it to try again, up to five steps.

![](./media/image93.png)

![](./media/image94.png)

![](./media/image95.png)

![](./media/image96.png)

![](./media/image97.png)

![](./media/image98.png)

![](./media/image99.png)

![](./media/image100.png)

**Note:** Your agent may quote matter notes (NOTE-) in its answers, because you are connected as the administrator.

### Task 5: Check the persistent memory

Enter exit, then run the following query in SQL:

```sql
SELECT message_id, role, LEFT(content, 100) AS content_start
FROM legal.agent_messages
WHERE session_id = 'lab4-demo'
ORDER BY message_id;
```

**Expected result:** The query returns the conversation history stored in the legal.agent_messages table for the lab4-demo session. The results are displayed in chronological order using message_id, showing three types of records:

- **user:** Questions submitted during the conversation.

- **tool:** Tool executions, including the tool name, arguments, and returned results.

- **assistant:** Responses generated by the agent, including final answers.

Each record is associated with the same session ID, allowing the agent to retrieve previous interactions.

![](./media/image101.png)

Checkpoint: You have a working GraphRAG agent whose tools, memory and audit trail all live in HorizonDB.

## Summary

In this lab, you built a GraphRAG-based Legal Research Agent on Azure HorizonDB by combining vector search, Apache AGE graph traversal, and relational document storage. You registered your own AI models, created SQL functions for model access, loaded legal documents and generated embeddings, and established citation relationships between documents. You then implemented a Python tool-calling agent that retrieves relevant legal evidence, expands its search through document relationships, and maintains persistent conversation memory using HorizonDB. Finally, you tested the agent's ability to answer legal research questions using retrieved evidence, recall previous interactions, and avoid generating unsupported answers when relevant information is unavailable.
