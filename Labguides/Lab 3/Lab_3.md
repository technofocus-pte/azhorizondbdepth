# Lab 3: Build Semantic and Hybrid Search Solutions for a Digital Media Platform on Azure HorizonDB

**Estimated duration:** 65 minutes,

## Scenario

StreamNova Media is a European streaming platform offering more than 12,000 movies, series, and documentaries. Lucía Moreno, Head of Discovery Engineering, wants to improve content discovery so viewers can find relevant titles even when their search terms do not exactly match the catalog descriptions.

The existing search experience presents two challenges:

- **Limited keyword understanding:** A viewer searching for “stealing money from a safe” may not find a title describing a “robbery of a high-security vault” because the wording differs.

- **Limited semantic precision:** A viewer searching for a specific title, character, or code name expects exact terms to influence the results. Semantic similarity alone may not consistently prioritize those terms.

To address these challenges, StreamNova wants to evaluate a search approach that combines lexical relevance with semantic similarity. As the platform engineer, you will build a prototype using Azure HorizonDB and its PostgreSQL extensions for AI-powered search.

You will prepare a synthetic media catalog, generate vector embeddings, configure BM25 and DiskANN indexes, and compare keyword-only, semantic, and hybrid retrieval. You will then combine rankings using Reciprocal Rank Fusion (RRF) and apply metadata filters to refine results for specific viewer requirements.

By the end of the lab, you will have a working prototype that demonstrates how different retrieval techniques can complement one another to improve content discovery.

## Objectives

After completing this lab, you will be able to:

1. Configure the required Azure HorizonDB extensions for AI-powered search.

2. Register an embedding model and generate vector embeddings for media catalog records.

3. Create BM25 and DiskANN indexes for keyword and vector retrieval.

4. Compare keyword-only, vector-only, and hybrid search results.

5. Combine keyword and vector rankings using Reciprocal Rank Fusion (RRF).

6. Evaluate retrieval behavior across different query types.

7. Apply metadata filters to narrow search results by content type and genre.

## Exercise 0: Set up the Azure HorizonDB environment

In this exercise, you will provision an Azure HorizonDB cluster, configure the PostgreSQL extensions required for search, register the embedding model, and create the lab database.

Complete the setup steps before proceeding to the search exercises. The catalog, indexes, and queries in the remaining exercises depend on this environment.

### Task 1: Create the HorizonDB cluster

Create a dedicated HorizonDB cluster for the StreamNova search prototype.

1. Open a web browser and navigate to +++https://portal.azure.com/+++.

2. Sign in using the following lab credentials:

   - **Username:** `@lab.CloudPortalCredential(User1).Username`

   - **TAP token:** `@lab.CloudPortalCredential(User1).AccessToken`

   ![A screenshot of a sign in box AI-generated content may be incorrect.](media/image1.png)

   ![A screenshot of a login screen AI-generated content may be incorrect.](media/image2.png)

   ![A screenshot of a computer AI-generated content may be incorrect.](media/image3.png)

3. In the search box at the top of the page, enter +++**Azure HorizonDB+++**. Under **Services**, select **Azure HorizonDB (Preview)**.

   ![](media/image4.png)

4. Select **Create**.

   ![](media/image5.png)

5. Configure the cluster using the following values. Leave settings not listed here at their defaults.

   | Setting | Value |
   | --- | --- |
   | Subscription | Your lab subscription |
   | Resource group | `ResourceGroup1` |
   | Cluster name | `streamnova-@lab.LabInstance.Id` |
   | Region | Central US |
   | PostgreSQL version | 17 |
   | Compute | 2 vCores, if available |
   | High availability | Disabled |
   | Authentication | PostgreSQL authentication |
   | Administrator username | `Mediaadmin` |
   | Password | `Pass@1234` |

   ![](media/image6.png)

   ![](media/image7.png)

6. Under **Firewall rules**, enable **Allow public access from any Azure service within Azure to this cluster**.

   ![](media/image8.png)

7. Select **Add current client IP address**, then select **Review + create**.

   ![](media/image9.png)

8. Review the configuration, select **Create**, and wait for the deployment to finish.

   ![](media/image10.png)

9. Select **Go to resource group**, open the HorizonDB cluster.

   ![](media/image11.png)

   ![](media/image12.png)

10. Copy the **Cluster endpoint** into notepad. You will need it when connecting through Visual Studio Code.

    ![](media/image13.png)

### Task 2: Create the parameter group and attach it to the cluster

Configure a parameter group to enable the PostgreSQL extensions required for vector search, keyword search, and AI-powered embedding generation.

1. In the left navigation pane, select **Settings > Parameters**.

   ![](media/image14.png)

2. Next to **Parameter group**, select **(create)**.

   ![](media/image15.png)

3. Enter the following values, then select **Next**.

   | Setting | Value |
   | --- | --- |
   | Resource Group | `ResourceGroup1` |
   | Parameter group name | `media-pg-@lab.LabInstance.Id` |
   | Region | Central US |
   | PostgreSQL version | 17 |
   | Parameter group (base) | PostgreSQL 17 |

4. Select **Next**.

   ![](media/image16.png)

5. Find the `azure.extensions` parameter and enable the following extensions:

   ```
   azure_ai, vector, pg_diskann, pg_textsearch
   ```

   ![](media/image17.png)

   ![](media/image18.png)

   ![](media/image19.png)

   ![](media/image20.png)

6. Find `shared_preload_libraries` and enable: `pg_textsearch`

   ![](media/image20.png)

7. Select **Create**.

   ![](media/image21.png)

8. Select **Go to resource**, then open the HorizonDB cluster.

   ![](media/image22.png)

9. Navigate to **Settings > Parameters** and select **(change)** next to **Parameter group**.

   ![](media/image23.png)

10. Select `media-pg-@lab.LabInstance.Id` and save the change.

    ![](media/image24.png)

11. The `azure.extensions` parameter is static, so attaching the parameter group triggers a cluster restart. Wait for the operation to finish.

    On the **Parameters** page, select **Refresh** and confirm that the parameter group is `media-pg-@lab.LabInstance.Id` and `azure.extensions` includes `azure_ai, vector, pg_diskann, and pg_textsearch`

    ![](media/image25.png)

**Note:** Parameter group deployment may take approximately 4–5 minutes. Allow additional time if the cluster requires a restart.

### Task 3: Configure the embedding model

The search solution needs an embedding model to convert catalog descriptions and viewer queries into vectors. These vectors allow HorizonDB to retrieve records based on semantic similarity rather than relying exclusively on matching words.

1. Reuse the embedding deployment from Lab 2 in Microsoft Foundry, such as `text-embedding-3-small`, which produces 1,536-dimensional embeddings.

2. Navigate to Foundry resource->Go to Foundry Portal to record the following deployment details for use in the subsequent tasks:

   - Endpoint URL

   - API key

   - Deployment name

   - Model name

   ![](media/image26.png)

### Task 4: Create the lab database and connect to it

Create a dedicated database for the StreamNova catalog so that the lab's tables, indexes, and search objects remain separate from other databases.

1. Open Visual Studio Code and navigate to the PostgreSQL extension.

   ![](media/image27.png)

   **Note:** If the PostgreSQL extension is not available, select **Extensions**, search for **PostgreSQL**, and install the appropriate extension.

2. Select **+ Add connection**.

   ![](media/image28.png)

3. Enter the following connection details.

   | Setting | Value |
   | --- | --- |
   | Server name | The primary endpoint saved in Exercise 0, Task 1 |
   | Authentication type | Password |
   | Administrator username | `Mediaadmin` |
   | Password | `Pass@1234` |
   | Server group | Servers |

   ![](media/image29.png)

4. Select **Test connection** to verify the connection.

   ![](media/image30.png)

5. After the test succeeds, select **Save & Connect**.

   ![](media/image31.png)

6. Select **New Query**.

   ![](media/image32.png)

7. Execute the following command to create the lab database:

   ```
   CREATE DATABASE streamnova_lab;
   ```

   ![](media/image33.png)

8. In the PostgreSQL extension's connection explorer, right-click the HorizonDB connection and select **Edit connection**.

   ![](media/image34.png)

9. Set the database name to `streamnova_lab`, then select **Save & Connect**.

   ![](media/image35.png)

10. After reconnecting, refresh the connection. It takes 4-5 mins to reflect the changes.

11. Open a new SQL query window and run the following command to verify the current database and connection:

    ```
    SELECT
        current_database() AS database_name,
        current_user AS connected_user;
    ```

**Expected result:** The database name is `streamnova_lab` and the connected user is `Mediaadmin`.

![](media/image36.png)

### Task 5: Enable the required extensions

Confirm that the cluster parameters are configured correctly, create the extensions in the lab database, and verify their installation.

1. Confirm the extension configuration by running:

   ```
   SHOW azure.extensions;
   SHOW shared_preload_libraries;
   ```

   **Expected result:** `azure.extensions` includes `azure_ai`, `vector`, `pg_diskann`, and `pg_textsearch`. `shared_preload_libraries` includes `pg_textsearch`.

   ![](media/image37.png)

2. Create the extensions:

   ```
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS pg_diskann CASCADE;
   CREATE EXTENSION IF NOT EXISTS pg_textsearch;
   CREATE EXTENSION IF NOT EXISTS azure_ai;
   ```

   ![](media/image38.png)

3. Verify the installation:

   ```
   SELECT extname, extversion
   FROM pg_extension
   WHERE extname IN ('vector', 'pg_diskann', 'pg_textsearch', 'azure_ai')
   ORDER BY extname;
   ```

   **Expected result:** All four extensions are listed. If an extension cannot be created, verify the cluster parameter configuration and ensure that you are connected to `streamnova_lab`.

   ![](media/image39.png)

### Task 6: Register your own models

Register the embedding deployment from Task 3 in the model registry. The registered alias, `my-embedding`, will be used by the SQL examples throughout the lab.

1. Replace the placeholders with the endpoint, deployment name, and API key recorded in Task 3. Use `NULL` for the API version to use the latest.

   **Embedding model**

   ```
   SELECT model_registry.model_add(
       'my-embedding',                               -- alias
       'https://<your-resource>.openai.azure.com/',  -- endpoint URL
       '<embedding-deployment-name>',                -- deployment name
       'text-embedding-3-small',                     -- model name
       NULL,                                         -- API version
       'subscription-key',                           -- auth type
       '<your-api-key>'                              -- API key
   );
   ```

   ![](media/image40.png)

2. Verify the registration:

   ```
   SELECT * FROM model_registry.model_list_all();
   ```

   **Expected result:** `my-embedding` appears in the model registry.

   ![](media/image41.png)

**Note:** The registered model must support embedding generation and produce vectors compatible with the catalog's `vector(1536)` column. Confirm the deployment configuration before proceeding.

## Exercise 1: Build semantic and hybrid search over the media catalog

In this exercise, you will build the StreamNova search foundation and test how different retrieval techniques respond to viewer queries.

You will create a catalog table, load sample records, generate embeddings, and create BM25 and DiskANN indexes. You will then run keyword-only and vector-only searches before combining their rankings using Reciprocal Rank Fusion (RRF).

The objective is to understand how lexical matching and semantic similarity contribute different signals to search results.

### Task 1: Create the catalog table

Create the schema and table that will store the StreamNova media catalog.

1. Open a new SQL query window connected to `streamnova_lab`.

2. Run the following SQL:

   ```
   CREATE SCHEMA IF NOT EXISTS media;

   CREATE TABLE media.titles (
       title_id     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
       title_name   VARCHAR(120) NOT NULL,
       content_type VARCHAR(20)  NOT NULL,
       genre        VARCHAR(30)  NOT NULL,
       release_year INT          NOT NULL,
       synopsis     TEXT         NOT NULL,
       search_text  TEXT,
       embedding    vector(1536)
   );
   ```

The `search_text` column will combine the title, genre, and synopsis into one searchable field for keyword ranking. The `embedding` column will store the vector representation used for semantic search.

![](media/image42.png)

### Task 2: Load the sample catalog

Populate the catalog with representative movies, series, and documentaries.

1. Run the following SQL to insert the sample records:

   ```
   INSERT INTO media.titles
       (title_name, content_type, genre, release_year, synopsis)
   VALUES
       ('Midnight Ledger', 'MOVIE', 'Thriller', 2021,
        'A forensic accountant uncovers a decades-old embezzlement scheme inside a prestigious bank.'),
       ('Harbor Lights', 'MOVIE', 'Drama', 2019,
        'A widowed fisherman and his estranged daughter rebuild the family boat shop after a violent storm.'),
       ('Code Name Falcon', 'MOVIE', 'Action', 2023,
        'An elite agent races across Europe to stop a rogue operative from selling stolen defence secrets.'),
       ('The Last Orchard', 'MOVIE', 'Drama', 2020,
        'Three generations of a farming family fight to save their apple orchard from a property developer.'),
       ('Neon District', 'SERIES', 'Sci-Fi', 2024,
        'In a rain-soaked cyberpunk city, a hacker discovers that her memories were edited by a mega-corporation.'),
       ('Laugh Track', 'SERIES', 'Comedy', 2022,
        'Two rival stand-up comedians are forced to share a tour bus across the country.'),
       ('Silent Orbit', 'MOVIE', 'Sci-Fi', 2022,
        'The crew of a failing space station must decide who returns to Earth on the last shuttle.'),
       ('Road Trip with Grandma', 'MOVIE', 'Family', 2018,
        'A feel-good journey as a retired teacher takes her grandchildren on a cross-country drive in a vintage camper van.'),
       ('Ironclad Heist', 'MOVIE', 'Action', 2023,
        'A crew of specialists plans an impossible robbery of a high-security vault during a city-wide blackout.'),
       ('Deep Blue Secrets', 'DOCUMENTARY', 'Documentary', 2021,
        'Marine biologists explore unmapped ocean trenches and discover species never seen before.'),
       ('The Bakery Cup', 'SERIES', 'Comedy', 2020,
        'A heartwarming comedy about a small-town bakery competing in a national baking contest.'),
       ('Shadow Protocol', 'MOVIE', 'Thriller', 2024,
        'A cybersecurity analyst realises that a government surveillance programme is spying on its own citizens.'),
       ('Moonlight Sonata', 'MOVIE', 'Drama', 2017,
        'A gifted but nearly deaf pianist prepares for a final concert while reconciling with her estranged mentor.'),
       ('Galaxy Rangers: Origins', 'SERIES', 'Animation', 2023,
        'Young cadets train to become interstellar peacekeepers in a lively animated space adventure.'),
       ('Planet Earth Rising', 'DOCUMENTARY', 'Documentary', 2022,
        'A visual journey through climate change and the communities adapting to rising seas.'),
       ('Cold Case Files: Harbor City', 'SERIES', 'Crime', 2021,
        'Detectives reopen unsolved murders from the nineties using new forensic techniques.');
   ```

   ![](media/image43.png)

2. Build the combined search text:

   ```
   UPDATE media.titles
   SET search_text = title_name || '. ' || genre || '. ' || synopsis;
   ```

   ![](media/image44.png)

3. Verify the number of records:

   ```
   SELECT COUNT(*) AS total_titles
   FROM media.titles;
   ```

   **Expected result:** `16`.

   ![](media/image45.png)

### Task 3: Generate embeddings

Generate a vector embedding for each catalog record using the registered embedding model. These embeddings represent the combined title, genre, and synopsis in a form that supports semantic similarity comparisons.

1. Run the following SQL:

   ```
   UPDATE media.titles
   SET embedding =
       azure_openai.create_embeddings(
           'my-embedding',
           search_text
       )::vector
   WHERE embedding IS NULL;
   ```

   ![](media/image46.png)

2. Verify that embeddings have been generated:

   ```
   SELECT
       COUNT(*) AS total_titles,
       COUNT(embedding) AS titles_with_embeddings
   FROM media.titles;
   ```

   **Expected result:** Both counts are `16`.

If the counts differ, verify that the embedding deployment is accessible and that the records have been processed successfully before continuing.

![](media/image47.png)

### Task 4: Create the BM25 and DiskANN indexes

Create indexes for the two retrieval methods used in the lab.

1. Create a BM25 index for keyword retrieval:

   ```
   CREATE INDEX idx_titles_bm25
   ON media.titles
   USING bm25 (search_text)
   WITH (text_config = 'english');
   ```

   ![](media/image48.png)

2. Create a DiskANN index for vector retrieval:

   ```
   CREATE INDEX idx_titles_vec
   ON media.titles
   USING diskann (embedding vector_cosine_ops);
   ```

The BM25 index supports lexical ranking, while the DiskANN index supports approximate nearest-neighbor retrieval over the embedding vectors.

![](media/image49.png)

### Task 5: Run a keyword-only search

In this task, you will use BM25 keyword search to retrieve titles from the StreamNova catalog. Compare an exact keyword with a related term to observe how lexical matching affects retrieval results.

#### Query 1: Search for an exact term

Search for titles matching the term `Falcon`.

1. Run the following query:

   ```
   SELECT
       title_name,
       genre,
       search_text <@> 'Falcon' AS bm25_score
   FROM media.titles
   ORDER BY search_text <@> 'Falcon'
   LIMIT 5;
   ```

   Review the returned titles and their BM25 scores.

   ![](media/image50.png)

#### Query 2: Search using a related keyword

Search for titles using the keyword `robbery`.

1. Run the following query:

   ```
   SELECT
       title_name,
       genre,
       search_text <@> 'robbery' AS bm25_score
   FROM media.titles
   ORDER BY search_text <@> 'robbery'
   LIMIT 5;
   ```

   Compare the results from both queries.

**Expected result:** Each query returns one or more catalog titles ranked by BM25 relevance, provided the catalog contains records. Results depend on the terms present in each title's searchable text.

![](media/image51.png)

### Task 6: Run a vector-only semantic search

In this task, you will generate an embedding for a natural-language query and use cosine distance to identify semantically related catalog records.

Unlike keyword retrieval, semantic search can identify conceptual relationships even when the query and catalog descriptions use different words.

1. Run the following query:

   ```
   WITH query_embedding AS (
       SELECT azure_openai.create_embeddings(
           'my-embedding',
           'stealing money from a safe'
       )::vector AS q_vec
   )
   SELECT
       t.title_name,
       t.genre,
       ROUND(
           (1 - (t.embedding <=> q.q_vec))::numeric,
           4
       ) AS similarity
   FROM media.titles AS t
   CROSS JOIN query_embedding AS q
   WHERE t.embedding IS NOT NULL
   ORDER BY t.embedding <=> q.q_vec
   LIMIT 5;
   ```

**Expected result:** `Ironclad Heist` should be a strong candidate because its synopsis describes a robbery of a high-security vault. Other relevant results may also appear. Exact ranking and similarity scores depend on the embedding model.

![](media/image52.png)

### Task 7: Run a hybrid search using RRF

In this task, you will combine keyword and semantic retrieval to produce a single ranked list.

Reciprocal Rank Fusion (RRF) combines the positions of results in multiple ranked lists without comparing their raw scores directly. This helps combine BM25 and vector rankings even though their scoring methods differ.

1. Run the following query to retrieve and combine the top BM25 and vector search results for the query `Harbor family drama`.

   ```
   WITH query_embedding AS (
       SELECT
           'Harbor family drama'::text AS q_text,
           azure_openai.create_embeddings(
               'my-embedding',
               'Harbor family drama'
           )::vector AS q_vec
   ),
   bm25 AS (
       SELECT
           t.title_id,
           ROW_NUMBER() OVER (
               ORDER BY t.search_text <@> to_bm25query(
                   q.q_text,
                   'media.idx_titles_bm25'
               )
           ) AS bm25_rank
       FROM media.titles AS t
       CROSS JOIN query_embedding AS q
       ORDER BY t.search_text <@> to_bm25query(
           q.q_text,
           'media.idx_titles_bm25'
       )
       LIMIT 20
   ),
   vec AS (
       SELECT
           t.title_id,
           ROW_NUMBER() OVER (
               ORDER BY t.embedding <=> q.q_vec
           ) AS vec_rank
       FROM media.titles AS t
       CROSS JOIN query_embedding AS q
       WHERE t.embedding IS NOT NULL
       ORDER BY t.embedding <=> q.q_vec
       LIMIT 20
   )
   SELECT
       t.title_name,
       t.genre,
       b.bm25_rank,
       v.vec_rank,
       ROUND(
           (
               1.0 / (60 + COALESCE(b.bm25_rank, 1000)) +
               1.0 / (60 + COALESCE(v.vec_rank, 1000))
           )::numeric,
           5
       ) AS rrf_score
   FROM media.titles AS t
   LEFT JOIN bm25 AS b ON b.title_id = t.title_id
   LEFT JOIN vec AS v ON v.title_id = t.title_id
   WHERE b.title_id IS NOT NULL
      OR v.title_id IS NOT NULL
   ORDER BY rrf_score DESC
   LIMIT 5;
   ```

**Expected result:** The query returns up to five titles ranked by their combined BM25 and vector rankings. `Harbor Lights` may rank highly because its title contains Harbor and its content may be semantically related to a family drama. Other titles may appear depending on the catalog content, embedding model, and individual rankings.

![](media/image53.png)

Compare the individual ranks with the combined RRF score to understand how both retrieval methods contribute to the final ordering.

## Exercise 2: Evaluate retrieval quality across queries and apply metadata filters

In this exercise, you will evaluate search behavior using different query phrases and refine results using catalog metadata.

Keyword and semantic search can return different candidates for the same general information need. Metadata filters provide another level of control by restricting results to specific content types or genres.

You will compare lexical and semantic retrieval for a space-related query, filter keyword results to comedy series, and filter semantic results to family movies. These activities demonstrate how retrieval methods and structured catalog attributes can work together to meet viewer requirements.

### Task 1: Evaluate search quality across query types

Evaluate how keyword and semantic search respond to different wording for a space-related information need.

#### Query 1: Run a keyword search

1. Run the following keyword query for the phrase `space station`:

   ```
   SELECT
       title_name,
       content_type,
       genre,
       search_text <@> to_bm25query(
           'space station',
           'media.idx_titles_bm25'
       ) AS bm25_score
   FROM media.titles
   WHERE search_text <@> to_bm25query(
       'space station',
       'media.idx_titles_bm25'
   ) < 0
   ORDER BY bm25_score
   LIMIT 5;
   ```

   Review the returned titles and their BM25 scores.

   ![](media/image54.png)

#### Query 2: Run a semantic search

1. Run the following query to search for the concept of a crew trying to survive in orbit:

   ```
   WITH query_embedding AS (
       SELECT azure_openai.create_embeddings(
           'my-embedding',
           'a crew trying to survive in orbit'
       )::vector AS q_vec
   )
   SELECT
       t.title_name,
       t.content_type,
       t.genre,
       ROUND(
           (1 - (t.embedding <=> q.q_vec))::numeric,
           4
       ) AS similarity
   FROM media.titles AS t
   CROSS JOIN query_embedding AS q
   WHERE t.embedding IS NOT NULL
   ORDER BY t.embedding <=> q.q_vec
   LIMIT 5;
   ```

**Expected result:** The keyword search ranks titles based on lexical relevance to `space station`. The semantic search ranks titles by vector similarity to `a crew trying to survive in orbit`, potentially finding conceptually related titles that use different wording.

![](media/image55.png)

Consider which method better identifies relevant titles when the query describes a concept rather than using the exact words found in a synopsis.

### Task 2: Apply metadata filters to keyword search (5 minutes)

A viewer wants to discover comedy series. Use a BM25 keyword query and filter the results by both content type and genre.

1. Run the following query:

   ```
   SELECT
       title_name,
       content_type,
       genre,
       search_text <@> to_bm25query(
           'comedy',
           'media.idx_titles_bm25'
       ) AS bm25_score
   FROM media.titles
   WHERE content_type = 'SERIES'
     AND genre = 'Comedy'
     AND search_text <@> to_bm25query(
         'comedy',
         'media.idx_titles_bm25'
     ) < 0
   ORDER BY bm25_score
   LIMIT 5;
   ```

   **Expected result:** Matching comedy series may be returned, such as `Laugh Track` and `The Bakery Cup`, if they match the keyword query and satisfy both metadata filters.

   ![](media/image56.png)

2. Inspect the metadata values in the catalog:

   ```
   SELECT
       content_type,
       genre,
       COUNT(*) AS title_count
   FROM media.titles
   GROUP BY content_type, genre
   ORDER BY content_type, genre;
   ```

   Review the grouped counts and observe how the catalog is distributed across content types and genres.

   Notice how metadata filters restrict the results to series in the Comedy genre. A filter can exclude relevant titles if its criteria are too restrictive.

   ![](media/image57.png)

### Task 3: Apply metadata filters to semantic search

A viewer wants a family-friendly movie described as “a heartwarming journey with children.” In this task, you will combine semantic retrieval with structured metadata filters to identify relevant movies while excluding other content types and genres.

1. Run the following semantic search while restricting the results to movies in the Family genre:

   ```
   WITH query_embedding AS (
       SELECT azure_openai.create_embeddings(
           'my-embedding',
           'a heartwarming journey with children'
       )::vector AS q_vec
   )
   SELECT
       t.title_name,
       t.content_type,
       t.genre,
       ROUND(
           (1 - (t.embedding <=> q.q_vec))::numeric,
           4
       ) AS similarity
   FROM media.titles AS t
   CROSS JOIN query_embedding AS q
   WHERE t.content_type = 'MOVIE'
     AND t.genre = 'Family'
     AND t.embedding IS NOT NULL
   ORDER BY t.embedding <=> q.q_vec
   LIMIT 5;
   ```

   **Expected result:** `Road Trip with Grandma` is the expected relevant title if its catalog record has the specified metadata and its embedding ranks it among the top results. The query returns up to five matching movies in the Family genre, ordered by vector similarity.

   ![](media/image58.png)

## Summary

In this lab, you built a semantic and hybrid search prototype for StreamNova Media using Azure HorizonDB and PostgreSQL extensions. You configured the environment, registered an embedding model, created a synthetic media catalog, generated vector embeddings, and configured BM25 and DiskANN indexes. You compared keyword-only and semantic search, combined their rankings using Reciprocal Rank Fusion (RRF), and applied metadata filters to refine results by content type and genre. You learned how combining keyword search, semantic similarity, and metadata filtering can improve content discovery. Before applying this approach to production, evaluate retrieval quality, indexing performance, latency, and embedding consistency using representative queries and larger datasets.
