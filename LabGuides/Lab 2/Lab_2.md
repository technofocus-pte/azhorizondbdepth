# Lab 2: Build an AI-Powered Fraud Detection System with Azure HorizonDB

**Duration-70 minutes**

**Scenario**

FinSecure Bank processes transactions across retail banking, card payments, ATM withdrawals, and wire transfers. Its fraud investigation team relies on predefined rules and manual reviews to identify suspicious activity. However, rule-based systems can miss transactions that resemble known fraud patterns without matching established rules, while investigators spend valuable time reviewing alerts and documenting potential risks.

To improve fraud detection, FinSecure Bank wants to build an AI-assisted fraud intelligence workflow using Azure HorizonDB. In this lab, you will use synthetic transaction data, vector embeddings, and DiskANN similarity search to identify transactions resembling known fraud patterns, assign preliminary risk bands, and generate AI-assisted explanations to support investigation.

The solution demonstrates how relational data, vector search, and AI inference can work together in a single database workflow. Similarity scores and AI-generated explanations are preliminary indicators, not proof of fraud; investigators must validate findings using independent evidence.

## Objectives

After completing this lab, you will be able to:

1. Configure Azure HorizonDB and allow-list the extensions required for AI inference and vector search.
2. Register custom embedding and chat models deployed in Microsoft Foundry with the HorizonDB model registry.
3. Create a relational schema and populate it with synthetic banking transactions and known fraud patterns.
4. Generate and store vector embeddings for transaction descriptions and fraud patterns.
5. Create DiskANN indexes and use vector similarity search to identify transactions resembling known fraud patterns.
6. Apply SQL-based risk thresholds and generate AI-assisted explanations to support fraud investigation.
7. Validate similarity matches and AI-generated explanations while distinguishing potential fraud indicators from confirmed fraud.

## Exercise 0: Set Up Azure HorizonDB and Configure Your AI Models

In this exercise, you will deploy an Azure HorizonDB cluster, configure a custom parameter group, and allow-list the extensions required for vector search and AI functions. You will also deploy embedding and chat models in Microsoft Foundry and prepare them for registration in HorizonDB.

**Task 1: Create the HorizonDB cluster**

1. Open a web browser and navigate to +++https://portal.azure.com/+++.
2. Sign in to the **Azure portal** using the following credentials:

    Username - +++@lab.CloudPortalCredential(User1).Username+++

    TAP Token - +++@lab.CloudPortalCredential(User1).AccessToken+++

    ![A screenshot of a sign in box AI-generated content may be incorrect.](media/image1.png)

    ![A screenshot of a login screen AI-generated content may be incorrect.](media/image2.png)

    ![A screenshot of a computer AI-generated content may be incorrect.](media/image3.png)

3. Select **Create a resource**.

    ![Screenshot](media/image4.png)

4. Search for +++**Azure HorizonDB**+++. Under **Azure HorizonDB (Preview)**, select **Create**, then **Azure HorizonDB (Preview)**.

    ![Screenshot](media/image5.png)

    ![Screenshot](media/image6.png)

5. Configure the cluster with the following settings, then select **Next**.

    | **Setting**            | **Suggested value**                                            |
    |------------------------|----------------------------------------------------------------|
    | Subscription           | Your lab subscription                                          |
    | Resource group         | ResourceGroup1                                                 |
    | Cluster name           | finsecure-hdb-lab                                              |
    | Region                 | Central US                                                     |
    | PostgreSQL version     | 17                                                             |
    | Compute                | 2 vCores, if available                                         |
    | High availability      | Disabled for the lowest-complexity learning setup, if optional |
    | Authentication         | PostgreSQL authentication                                      |
    | Administrator username | Finadmin                                                       |
    | Password               | Pass@1234                                                      |

    Select **Next**.

    ![Screenshot](media/image7.png)

    ![Screenshot](media/image8.png)

6. Under **Firewall rule**, enable **Allow public access from any Azure service within Azure to this cluster**.

    ![Screenshot](media/image9.png)

7. Select **Add your current public IP address to the firewall allowlist**, then select **Review + create**.

    ![Screenshot](media/image10.png)

    ![Screenshot](media/image11.png)

8. Select **Create.**

    ![Screenshot](media/image12.png)

9. Wait 10-15 minutes for the deployment to finish.

    ![Screenshot](media/image13.png)

10. Select **Go to resource group**, then open the cluster.

    ![Screenshot](media/image14.png)

    ![Screenshot](media/image15.png)

11. Copy the **Cluster endpoint** into a text editor. You will use it in the next exercises.

    ![Screenshot](media/image16.png)

**Task 2: Create a parameter group and allow-list the extensions**

HorizonDB rejects CREATE EXTENSION unless the extension is listed in the azure.extensions server parameter, even for the administrator. The cluster starts on the Default parameter group, which is read-only and has an empty azure.extensions value.

1. In the Azure portal, open the cluster **finsecure-hdb-lab** and select **Settings > Parameters**.

    ![Screenshot](media/image17.png)

2. Next to **Parameter group**, select **(create)**.

    ![Screenshot](media/image18.png)

3. On the **Create a parameter group** page, enter the following values, then select **Next**.

    | **Setting**            | **Value**                           |
    |------------------------|-------------------------------------|
    | Subscription           | Your lab subscription               |
    | Resource group         | ResourceGroup1                      |
    | Parameter group name   | finsecure-pg                        |
    | Region                 | Central US (must match the cluster) |
    | PostgreSQL version     | 17                                  |
    | Parameter group (base) | PostgreSQL 17                       |

    Select **Next.**

    ![Screenshot](media/image19.png)

4. On the parameters page, filter for +++**azure.extensions**+++ and from the parameter drop down select the following values: azure_ai, vector, pg_diskann

    ![Screenshot](media/image20.png)

    ![Screenshot](media/image21.png)

    ![Screenshot](media/image22.png)

    ![Screenshot](media/image23.png)

5. Select **Create**.

    ![Screenshot](media/image24.png)

6. Select Got to resource -> open the HorizonDB cluster.

    Note: Deployment takes 4-5 mins to complete.

    ![Screenshot](media/image25.png)

    ![Screenshot](media/image26.png)

7. Open **Settings > Parameters**, and select **(change)** next to **Parameter group**.

    ![Screenshot](media/image27.png)

8. Select **finsecure-pg** and save.

    ![Screenshot](media/image28.png)

9. The azure.extensions parameter is static, so the cluster restarts automatically when you attach the group.
10. On the **Parameters** page, select **Refresh** and confirm that the parameter group is **finsecure-pg** and azure.extensions shows azure_ai, vector, and pg_diskann.

    ![Screenshot](media/image29.png)

**Task 3: Configure AI models**

In this task you deploy the models and record their details.

1. In the search bar enter +++Foundry+++ and select **Microsoft Foundry** from the search result.

    ![Screenshot](media/image30.png)

2. Open the Microsoft Foundry portal and select (or create) a project.

    ![Screenshot](media/image31.png)

3. Select **Create**.

    ![Screenshot](media/image32.png)

4. Enter the following details to create a Foundry project:

    | Setting              | Suggested value             |
    |----------------------|-----------------------------|
    | Resource Group       | ResourceGroup1              |
    | Name                 | Foundry @lab.LabInstance.Id |
    | Region               | Central US                  |
    | Default Project Name | project@lab.LabInstance.Id  |

    Select Review+create.

    ![Screenshot](media/image33.png)

    ![Screenshot](media/image34.png)

5. Select **Create**.

    ![Screenshot](media/image35.png)

6. Select **Go to resource**.

    ![Screenshot](media/image36.png)

7. Select **Go to Foundry portal**.

    ![Screenshot](media/image37.png)

8. In the Use model section select view deployments.

    ![Screenshot](media/image38.png)

9. Select **Deploy a base model**.

    ![Screenshot](media/image39.png)

10. Search +++text-embedding in the search bar. Then select **text-embedding-3-small** model.

    ![Screenshot](media/image40.png)

11. Select Deploy->Default settings.

    ![Screenshot](media/image41.png)

12. Save the value of Endpoint and key in the notepad you will use them in the upcoming tasks.

    ![Screenshot](media/image42.png)

13. Now deploy chat model. Select **Deploy a base model**.

    ![Screenshot](media/image43.png)

14. So search for +++gpt-5.1+++ in the search bar and then select gpt-5.1 model from the search result.

    ![Screenshot](media/image44.png)

15. Select Deploy ->Default settings.

    ![Screenshot](media/image45.png)

16. Save the Endpoint and key values in the notepad we will use them in the upcoming task.

    ![Screenshot](media/image46.png)

17. Choose an alias for each model. This lab uses **my-embedding** for the embedding model and **my-gpt** for the chat model.

In Option B, every AI function call in Exercises 2 and 4 must pass your alias. The lab shows both variants.

## Exercise 1: Prepare the Fraud Intelligence Database

In this exercise, you will connect to your HorizonDB cluster, create a dedicated database, enable the required extensions, and register your Foundry models using custom aliases. You will then create the FinSecure fraud intelligence schema and populate it with synthetic banking transactions and known fraud patterns.

**Task 1: Create the lab database**

1. Open Visual Studio code and navigate to PostgreSQL extension.

    Note: If the PostgresSQL extension is not available in the VS code go to extensions->search for PostgresSQL->select install.

    ![Screenshot](media/image47.png)

2. Select **+Add connection**.

    ![Screenshot](media/image48.png)

3. Enter the following connection details:

    | Setting             | Suggested value                                                                 |
    |---------------------|---------------------------------------------------------------------------------|
    | Server name         | Primary endpoint of the cluster which we saved in Exercise 0->Task 1->step 10 |
    | Authentication Type | Password                                                                        |
    | Username            | Finadmin                                                                        |
    | Password            | Pass@1234                                                                       |
    | Server Group        | Servers                                                                         |

    Select **Test connection** to check the connection.

    ![Screenshot](media/image49.png)

    ![Screenshot](media/image50.png)

4. After running Test connection successfully select **Save & Connect**.

    ![Screenshot](media/image51.png)

5. Select **New Query**.

    ![Screenshot](media/image52.png)

6. Create a new database using the following command and hit Play button to execute Query:

    ```sql
    +++CREATE DATABASE finsecure_lab;+++
    ```

    ![Screenshot](media/image53.png)

    Your new database is created.

    ![Screenshot](media/image54.png)

**Task 2: Connect to the lab database and verify the environment**

1. Navigate to the HorizonDB cluster and right-click on it you will get a dropdown and select **Edit connection**.
2. In Visual Studio Code, connect to the cluster again and select the **finsecure_lab** database.
3. Extensions and the model registry are per database, so all remaining statements must run in finsecure_lab.

    ![Screenshot](media/image55.png)

4. Enter database name as +++ **finsecure_lab**+++ and select **Save & Connect.** After few mins refresh the cluster.

    ![Screenshot](media/image56.png)

5. Open a new SQL query window and run the following command to verify the current database.:

    ```sql
    SELECT
      current_database() AS database_name,
      current_user AS connected_user,
      version() AS postgres_version;
    ```

    Expected result: database_name shows finsecure_lab, along with the connected user and the PostgreSQL-compatible server version.

    ![Screenshot](media/image57.png)

**Task 3: Enable the required extensions**

1. Run the following query to confirm that the required extensions are included in the allow-list configured in Exercise 0, Task 2.

    ```sql
    +++SHOW azure.extensions;+++
    ```

    Verify that the output includes azure_ai, vector, and pg_diskann.

    Note: If the output is empty or any required extension is missing, the parameter group may not be attached correctly, or the cluster may not have finished restarting. Return to Exercise 0, Task 2, and verify the configuration before proceeding.

    ![Screenshot](media/image58.png)

2. Run the following commands to install the extensions in the current database.

    ```sql
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pg_diskann CASCADE;
    CREATE EXTENSION IF NOT EXISTS azure_ai;
    ```

    ![Screenshot](media/image59.png)

3. Run the following query to confirm that all three extensions are installed.

    ```sql
    SELECT extname, extversion
    FROM pg_extension
    WHERE extname IN ('vector', 'pg_diskann', 'azure_ai')
    ORDER BY extname;
    ```

    Expected result: The query returns three rows, listing azure_ai, pg_diskann, and vector, along with their installed versions.

    ![Screenshot](media/image60.png)

**Task 4: Register your own models**

1. Replace the placeholders with the values you recorded in Exercise 0, Task 3. Use NULL for the API version to use the latest.

    ```sql
    -- Embedding model
    SELECT model_registry.model_add(
      'my-embedding',                                -- alias
      'https://<your-resource>.openai.azure.com/',   -- endpoint URL
      '<embedding-deployment-name>',                 -- deployment name
      'text-embedding-3-small',                      -- model name
      NULL,                                          -- API version
      'subscription-key',                            -- auth type
      '<your-api-key>'                               -- API key
    );

    -- Chat model
    SELECT model_registry.model_add(
      'my-gpt',
      'https://<your-resource>.openai.azure.com/',
      '<chat-deployment-name>',
      'gpt-5.1',
      NULL,
      'subscription-key',
      '<your-api-key>'
    );
    ```

2. Verify the registration:

    ```sql
    SELECT * FROM model_registry.model_list_all();
    ```

    Expected result: my-embedding and my-gpt appear in the list.

    ![Screenshot](media/image61.png)

**Task 5: Create the FinSecure Schema, Tables, and Sample Data**

1. Run the following command to create the schema that will contain the fraud detection tables.

    ```sql
    CREATE SCHEMA IF NOT EXISTS finsecure;
    ```

    ![Screenshot](media/image62.png)

2. Run the following command to store synthetic banking transactions, risk classifications, vector embeddings, and analyst notes.

    ```sql
    CREATE TABLE finsecure.transactions (
      txn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      txn_timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
      account_ref VARCHAR(20) NOT NULL,
      txn_amount NUMERIC(12, 2) NOT NULL,
      currency_code CHAR(3) NOT NULL,
      txn_channel VARCHAR(20) NOT NULL,
      txn_memo TEXT NOT NULL,
      risk_band VARCHAR(10) DEFAULT 'UNASSESSED',
      txn_embedding vector(1536),
      analyst_notes TEXT
    );
    ```

    The following columns support the AI-powered fraud detection workflow:

    | **Column**    | **Purpose**                                               |
    |---------------|-----------------------------------------------------------|
    | txn_embedding | Stores the vector representation of the transaction memo. |
    | risk_band     | Stores the result of SQL-based risk classification.       |
    | analyst_notes | Stores the generated and reviewed explanation.            |

    ![Screenshot](media/image63.png)

3. Run the following command to store known fraud patterns for comparison with transaction descriptions.

    ```sql
    CREATE TABLE finsecure.fraud_patterns (
      pattern_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      pattern_name VARCHAR(100) NOT NULL,
      pattern_description TEXT NOT NULL,
      pattern_embedding vector(1536)
    );
    ```

    ![Screenshot](media/image64.png)

4. Run the following SQL statement to populate the table with five synthetic fraud patterns.

    ```sql
    INSERT INTO finsecure.fraud_patterns
      (pattern_name, pattern_description)
    VALUES
      ('Structuring', 'Repeated cash deposits or withdrawals just below reporting thresholds.'),
      ('Synthetic Identity Fraud', 'New or manipulated identities used to obtain credit and rapidly exhaust available funds.'),
      ('Card Not Present Fraud', 'Suspicious online purchases with unusual device, location, or payment behaviour.'),
      ('Business Email Compromise', 'Urgent wire transfers to a new beneficiary following suspected email impersonation.'),
      ('Money Mule Activity', 'Rapid movement of funds through multiple accounts, followed by onward transfers.');
    ```

    ![Screenshot](media/image65.png)

5. Run the following SQL statement to populate the transactions table with eight synthetic banking transactions.

    ```sql
    INSERT INTO finsecure.transactions
      (account_ref, txn_amount, currency_code, txn_channel, txn_memo)
    VALUES
      ('ACCT-1001', 9800.00, 'GBP', 'ATM', 'Several cash withdrawals just below the reporting threshold.'),
      ('ACCT-1002', 12500.00, 'GBP', 'WIRE', 'Urgent transfer to a newly added beneficiary after an email request.'),
      ('ACCT-1003', 349.99, 'GBP', 'ONLINE', 'Online purchase with an unfamiliar device and unusual location.'),
      ('ACCT-1004', 7500.00, 'GBP', 'TRANSFER', 'Funds received and transferred to multiple new accounts within minutes.'),
      ('ACCT-1005', 120.00, 'GBP', 'POS', 'Regular supermarket purchase using an established payment card.'),
      ('ACCT-1006', 8900.00, 'GBP', 'ATM', 'Multiple cash withdrawals across branches during the same day.'),
      ('ACCT-1007', 4800.00, 'GBP', 'WIRE', 'Payment to a supplier following a request to change bank details.'),
      ('ACCT-1008', 85.50, 'GBP', 'ONLINE', 'Routine online purchase from a previously used merchant.');
    ```

6. Run the following query to confirm that the transactions were inserted successfully.

    ![Screenshot](media/image66.png)

    ```sql
    SELECT
      txn_id,
      account_ref,
      txn_amount,
      currency_code,
      txn_channel,
      txn_memo,
      risk_band
    FROM finsecure.transactions
    ORDER BY txn_timestamp DESC;
    ```

    **Expected result:** Eight synthetic transactions appear, each with a generated transaction ID and an initial risk band of UNASSESSED.

    ![Screenshot](media/image67.png)

You have created the finsecure schema, created the transactions and fraud-pattern tables, and populated both tables with synthetic training data. The tables are ready for the subsequent fraud classification and AI-powered analysis exercises.

## Exercise 2: Generate and Store Vector Embeddings

In this exercise, you will use your registered embedding model to convert transaction descriptions and known fraud patterns into vector embeddings. You will store the embeddings in HorizonDB and verify that they are ready for similarity-based fraud detection.

**1.** Run the following query to confirm that the my-embedding model generates 1,536-dimensional vectors.

```sql
SELECT azure_openai.create_embeddings(
  'my-embedding',
  'Repeated cash withdrawals just below a reporting threshold.'
) AS test_embedding;
```

**Expected result:** The query returns a vector containing 1,536 dimensions. If the query fails, resolve the embedding model configuration issue before proceeding.

![Screenshot](media/image68.png)

**2.** Run the following statement to generate and store embeddings for transaction descriptions that do not already have them.

```sql
UPDATE finsecure.transactions
SET txn_embedding = azure_openai.create_embeddings(
  'my-embedding',
  txn_memo
)::vector
WHERE txn_embedding IS NULL;
```

![Screenshot](media/image69.png)

**3.** Run the following statement to generate and store embeddings using each fraud pattern's name and description.

```sql
UPDATE finsecure.fraud_patterns
SET pattern_embedding = azure_openai.create_embeddings(
  'my-embedding',
  pattern_name || ': ' || pattern_description
)::vector
WHERE pattern_embedding IS NULL;
```

![Screenshot](media/image69.png)

**4.** Run the following query to verify that all eight transactions have embeddings.

```sql
SELECT
  COUNT(*) AS total_transactions,
  COUNT(txn_embedding) AS transactions_with_embeddings
FROM finsecure.transactions;
```

![Screenshot](media/image70.png)

Next, run the following query to verify that all five fraud patterns have embeddings.

```sql
SELECT
  pattern_name,
  pattern_embedding IS NOT NULL AS embedding_created
FROM finsecure.fraud_patterns
ORDER BY pattern_id;
```

**Expected result:** The transaction query returns 8 for both total_transactions and transactions_with_embeddings. The fraud-pattern query returns five rows, each showing true in the embedding_created column.

![Screenshot](media/image71.png)

If any embeddings are missing, resolve the model configuration issue and rerun the relevant UPDATE statement. The WHERE ... IS NULL condition ensures that only records without embeddings are processed.

Both tables contain 1,536-dimensional vector embeddings ready for similarity-based fraud detection.

## Exercise 3: Detect Similar Fraud Patterns and Assign Risk Bands

In this exercise, you will create DiskANN indexes and use cosine similarity to identify transactions that resemble known fraud patterns. You will compare the closest pattern matches and assign preliminary risk bands using SQL-based similarity thresholds.

**1.** Create a DiskANN index for transactions by running the following statement.

```sql
CREATE INDEX transactions_embedding_diskann_idx
ON finsecure.transactions
USING diskann (txn_embedding vector_cosine_ops);
```

![Screenshot](media/image72.png)

**2.** Create a DiskANN index for fraud patterns by running the following statement.

```sql
CREATE INDEX fraud_patterns_embedding_diskann_idx
ON finsecure.fraud_patterns
USING diskann (pattern_embedding vector_cosine_ops);
```

**Note:** Because this lab uses a small dataset, the query planner might choose a sequential scan instead of using the DiskANN indexes.

![Screenshot](media/image73.png)

**3.** Search for transactions resembling structuring by comparing transaction embeddings with the stored embedding for the *Structuring* fraud pattern.

```sql
WITH selected_pattern AS (
  SELECT pattern_id, pattern_name, pattern_embedding
  FROM finsecure.fraud_patterns
  WHERE pattern_name = 'Structuring'
)
SELECT
  t.txn_id,
  t.account_ref,
  t.txn_amount,
  t.currency_code,
  t.txn_channel,
  t.txn_memo,
  p.pattern_name AS matched_pattern,
  ROUND(
    (1 - (t.txn_embedding <=> p.pattern_embedding))::numeric,
    4
  ) AS similarity_score
FROM finsecure.transactions AS t
CROSS JOIN selected_pattern AS p
WHERE t.txn_embedding IS NOT NULL
  AND p.pattern_embedding IS NOT NULL
ORDER BY t.txn_embedding <=> p.pattern_embedding
LIMIT 5;
```

The <=> operator calculates cosine distance. Subtracting the distance from 1 produces the cosine similarity score.

**Expected result:** Up to five transactions are returned, ordered from closest to least similar to the Structuring pattern. The two cash-withdrawal descriptions may rank highly. Actual scores depend on the embedding model.

![Screenshot](media/image74.png)

**4.** Find the closest fraud pattern for each transaction by running the following query.

```sql
SELECT
  t.txn_id,
  t.account_ref,
  t.txn_amount,
  t.txn_channel,
  t.txn_memo,
  matched.pattern_name AS closest_fraud_pattern,
  ROUND(matched.similarity_score::numeric, 4) AS similarity_score
FROM finsecure.transactions AS t
CROSS JOIN LATERAL (
  SELECT
    fp.pattern_name,
    1 - (t.txn_embedding <=> fp.pattern_embedding) AS similarity_score
  FROM finsecure.fraud_patterns AS fp
  WHERE t.txn_embedding IS NOT NULL
    AND fp.pattern_embedding IS NOT NULL
  ORDER BY t.txn_embedding <=> fp.pattern_embedding
  LIMIT 1
) AS matched
ORDER BY similarity_score DESC;
```

**Expected result:** Each transaction with a valid embedding is paired with its closest matching fraud pattern. Compare the matched patterns and similarity scores with the original transaction descriptions.

![Screenshot](media/image75.png)

**5.** Assign risk bands based on similarity scores. The following thresholds are illustrative values for this lab, not validated fraud-detection thresholds.

| **Maximum similarity score** | **Risk band** |
|------------------------------|---------------|
| 0.70 or higher               | CRITICAL      |
| 0.60 to below 0.70           | HIGH          |
| 0.55 to below 0.60           | MEDIUM        |
| Below 0.55                   | LOW           |

Run the following statement to calculate each transaction's maximum similarity to any stored fraud pattern and update its risk band.

```sql
WITH transaction_scores AS (
  SELECT
    t.txn_id,
    MAX(1 - (t.txn_embedding <=> fp.pattern_embedding))
      AS max_similarity
  FROM finsecure.transactions AS t
  CROSS JOIN finsecure.fraud_patterns AS fp
  WHERE t.txn_embedding IS NOT NULL
    AND fp.pattern_embedding IS NOT NULL
  GROUP BY t.txn_id
)
UPDATE finsecure.transactions AS t
SET risk_band =
  CASE
    WHEN s.max_similarity >= 0.70 THEN 'CRITICAL'
    WHEN s.max_similarity >= 0.60 THEN 'HIGH'
    WHEN s.max_similarity >= 0.55 THEN 'MEDIUM'
    ELSE 'LOW'
  END
FROM transaction_scores AS s
WHERE t.txn_id = s.txn_id;
```

![Screenshot](media/image76.png)

**6.** Review the risk classification by running the following query to display the highest risk categories first.

```sql
SELECT
  account_ref,
  txn_amount,
  txn_channel,
  txn_memo,
  risk_band
FROM finsecure.transactions
ORDER BY
  CASE risk_band
    WHEN 'CRITICAL' THEN 1
    WHEN 'HIGH' THEN 2
    WHEN 'MEDIUM' THEN 3
    ELSE 4
  END,
  txn_amount DESC;
```

**Expected result:** Transactions are displayed in risk-band order, from CRITICAL to LOW, with higher-value transactions listed first within each category.

![Screenshot](media/image77.png)

**Important:** A high similarity score does not establish that a transaction is fraudulent. Similarity-based results are preliminary indicators; investigators must validate alerts using additional evidence and business rules.

**Checkpoint:** You have created DiskANN indexes, retrieved similar fraud patterns using vector distance, identified the closest pattern for each transaction, and assigned illustrative risk bands based on similarity scores.

## Exercise 4: Generate an AI-Assisted Risk Explanation

In this exercise, you will use your registered chat model with a HorizonDB AI function to generate an explanation for a potentially high-risk transaction. You will review the output for accuracy and unsupported claims, then save the reviewed explanation in the database for further investigation.

**1.** Select a flagged transaction by running the following query.

```sql
SELECT
  txn_id,
  account_ref,
  txn_amount,
  currency_code,
  txn_channel,
  txn_memo,
  risk_band
FROM finsecure.transactions
WHERE risk_band IN ('HIGH', 'CRITICAL')
ORDER BY txn_amount DESC
LIMIT 5;
```

Note: If no rows are returned, review the results from Exercise 3. Model-dependent similarity scores might not reach HIGH or CRITICAL with the demonstration thresholds. Adjust the training thresholds only if necessary.

![Screenshot](media/image78.png)

Copy a transaction UUID from the returned row(named as txn_id) we will use it in the upcoming step.

**2.** Generate a risk explanation by running the following query. The query uses the configured default chat model unless you specify the my-gpt model alias.

```sql
SELECT
  txn_id,
  account_ref,
  txn_amount,
  currency_code,
  txn_channel,
  risk_band,
  azure_ai.generate(
    prompt =>
      'Review this synthetic banking transaction for a human fraud investigator. '
      || 'Explain the observed suspicious indicators, possible matching fraud '
      || 'typology, and recommended verification steps. Clearly distinguish '
      || 'observed facts from hypotheses. Do not claim that fraud is confirmed. '
      || 'Transaction reference: ' || account_ref
      || '; amount: ' || txn_amount::text || ' ' || currency_code
      || '; channel: ' || txn_channel
      || '; risk band: ' || risk_band
      || '; memo: ' || txn_memo,
    system_prompt =>
      'You assist financial crime investigators. Use only the supplied '
      || 'transaction details. Do not invent evidence, customer history, '
      || 'sanctions matches, or regulatory findings. Return a concise '
      || 'draft for human review.',
    model => 'my-gpt'
  ) AS risk_explanation
FROM finsecure.transactions
WHERE risk_band IN ('HIGH', 'CRITICAL')
ORDER BY txn_amount DESC
LIMIT 1;
```

**Expected result:** The query returns one transaction and an AI-generated draft describing potential risk indicators and recommended verification steps. Review the explanation for accuracy and confirm that it does not introduce evidence absent from the transaction record.

![Screenshot](media/image79.png)

**3.** Save the reviewed draft in analyst_notes. Replace the placeholder with the transaction UUID returned in step 1 and replace the sample note with your reviewed explanation.

```sql
UPDATE finsecure.transactions
SET analyst_notes =
  'Draft reviewed by the training analyst. '
  || 'Verify the transaction against independent evidence.'
WHERE txn_id = '<transaction-uuid>'::uuid;
```

Before executing the statement, replace the sample note with your actual reviewed explanation and ensure the UUID identifies the correct transaction.

![Screenshot](media/image80.png)

You have selected a flagged transaction, generated an AI-assisted risk explanation, reviewed the output, and saved the reviewed draft in the database for further investigation.

## Exercise 5: Validate the Fraud Intelligence Results

In this exercise, you will combine transaction details, risk classifications, matching fraud patterns, similarity scores, and analyst notes in a consolidated query. You will review the results to understand how custom AI models and vector search support fraud investigation while recognizing that potential risks require independent verification.

**1.** Review the fraud intelligence results by running the following query.

```sql
SELECT
  t.txn_id, t.txn_timestamp, t.account_ref, t.txn_amount,
  t.currency_code, t.txn_channel, t.txn_memo, t.risk_band,
  matched.pattern_name AS closest_fraud_pattern,
  ROUND(matched.similarity_score::numeric, 4) AS similarity_score,
  t.analyst_notes
FROM finsecure.transactions AS t
LEFT JOIN LATERAL (
  SELECT fp.pattern_name,
    1 - (t.txn_embedding <=> fp.pattern_embedding) AS similarity_score
  FROM finsecure.fraud_patterns AS fp
  WHERE t.txn_embedding IS NOT NULL
    AND fp.pattern_embedding IS NOT NULL
  ORDER BY t.txn_embedding <=> fp.pattern_embedding
  LIMIT 1
) AS matched ON TRUE
ORDER BY
  CASE t.risk_band
    WHEN 'CRITICAL' THEN 1
    WHEN 'HIGH' THEN 2
    WHEN 'MEDIUM' THEN 3
    ELSE 4
  END,
  similarity_score DESC NULLS LAST;
```

**Expected result:** The query returns transaction details, risk classifications, the nearest matching fraud pattern, similarity scores, and any saved analyst notes. Transactions are ordered by risk classification, with the highest similarity scores listed first within each risk category.

![Screenshot](media/image81.png)

You have reviewed the fraud intelligence results and can compare the assigned risk bands with the matching fraud patterns, similarity scores, and analyst notes.

## Exercise 6: Clean Up Lab Resources

In this exercise, you will delete the Azure resources created for the lab to avoid ongoing charges after completing the fraud detection workflow.

1. In the Azure portal, open **ResourceGroup1**.
2. Select all the resources present in the resource group. Then select the three-dot (**...**) menu and choose **Delete**.

    ![Screenshot](media/image82.png)

3. Enter delete to confirm, then select **Delete**.

**Summary**

In this lab, you allow-listed the required extensions with a custom parameter group, configured AI models (managed or your own), and built a simplified AI-powered fraud detection workflow using Azure HorizonDB. You created a relational data model for synthetic banking transactions and fraud patterns, generated embeddings with HorizonDB AI functions, used DiskANN for vector similarity search, assigned risk bands with SQL, and generated an AI-assisted explanation for investigator review.

These capabilities show how a PostgreSQL-compatible platform can combine structured transaction data, semantic retrieval, and AI inference within a single database workflow.
