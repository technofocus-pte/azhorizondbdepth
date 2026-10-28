# Lab 4 — Build a GraphRAG Legal Research Agent on Azure HorizonDB

## Lab scenario

Calder & Voss LLP is a law firm that advises employers. Its associates research questions such as Can a court narrow an overbroad non-compete instead of striking it down? The answer is rarely in one document. It sits in a chain of court opinions that cite each other, in firm research memos that summarize them, and in matter notes that apply them to a client.

A plain vector search finds the single closest document. It does not know that other documents are connected to it by citation. In this lab you combine three things in one PostgreSQL database:

1. **Vector search** (pgvector) finds the document closest to the question.
2. **A citation graph** (Apache AGE) finds the cases it relies on and the later documents that rely on it.
3. **The relational table** holds the authoritative text of every document.

Then you wrap these as tools for an agent. The agent decides which tool to call, remembers the conversation in HorizonDB, and answers only from what the tools return. This pattern is called GraphRAG. It follows the approach of the GraphRAG Legal Research Copilot sample (https://github.com/Azure-Samples/graphrag-legalcases-postgres), scaled down to fit a 60-minute lab.

## Learning objectives

After this lab you can:

1. Wrap managed AI models in SQL functions so applications never call model functions directly.
2. Combine vector similarity and graph traversal in one retrieval flow, with no hardcoded document IDs.
3. Query an Apache AGE graph from a SQL function.
4. Build a tool-calling agent in Python that uses HorizonDB for retrieval and persistent memory.
5. Check that an agent's answers are grounded in retrieved documents.


## Exercise 0: Environment setup 


### Task 1: Create the cluster

1. In the Azure portal, search for Azure HorizonDB, select Azure HorizonDB (Preview), then select Create. Do not choose Azure Database for PostgreSQL Flexible Server.
2. Use these values and leave everything else at its default.

| Setting | Value |
|---|---|
| Resource group | ResourceGroup1 |
| Cluster name | legalai-hdb-lab (add a unique suffix if taken) |
| Region | Central US |
| PostgreSQL version | 17 |
| Compute | 4 vCores if available (2 vCores also works, but Lab 6 runs slower) |
| High availability | Disabled |
| Authentication | PostgreSQL authentication |
| Administrator username | lawadmin |
| Password | Pass@1234 (lab use only; use a different value in a shared subscription) |
| Networking | Public access, allow Azure services, add the client IP address |

3. Select Create and wait 5 to 10 minutes. Copy the Cluster endpoint.

### Task 2: Create and attach the parameter group

1. Open the cluster, select Settings > Parameters, then next to Parameter group select (create).
2. Name it legalai-pg, region Central US, PostgreSQL 17, base group PostgreSQL 17.
3. Enable these values for azure.extensions: azure_ai, vector, pg_diskann, age.
4. Enable age for shared_preload_libraries.
5. Create the group, attach it to the cluster (change > legalai-pg), and wait for the automatic restart to finish.

Important: If age is not preloaded, the first Cypher query fails with unhandled cypher(cstring) function call error. Do not run LOAD 'age';.

### Task 3: Enable managed AI models

Open AI model manager in the cluster menu, select Enable managed models, save, and accept the terms. The default-embedding alias and the default chat model become available.

### Task 4: Create the lab database and extensions

Connect to the postgres database with Visual Studio Code (host = cluster endpoint, port 5432, user lawadmin, SSL mode Require) and run:

```
CREATE DATABASE legalai_lab;
```

Open a new connection to legalai_lab and run:

```
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_diskann CASCADE;
CREATE EXTENSION IF NOT EXISTS azure_ai;
CREATE EXTENSION IF NOT EXISTS age CASCADE;

SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('vector', 'pg_diskann', 'azure_ai', 'age')
ORDER BY extname;
```

Expected result: all four extensions are listed.

## Exercise 1: Load the research library and build the citation graph (15 minutes)

All statements in Exercises 1 and 2 run in legalai_lab.

### Task 1: Wrap the AI models in SQL functions

The application never calls the model functions directly. It calls two small wrappers. In Lab 7 you lock these down so users cannot call the models themselves, and if you use your own models you only change them here.

```
CREATE SCHEMA IF NOT EXISTS legal;

CREATE OR REPLACE FUNCTION legal.embed(p_text text)
RETURNS vector
LANGUAGE sql STABLE
AS $$ SELECT azure_openai.create_embeddings(input => p_text)::vector $$;

CREATE OR REPLACE FUNCTION legal.llm(p_prompt text, p_system text)
RETURNS text
LANGUAGE sql
AS $$ SELECT azure_ai.generate(prompt => p_prompt, system_prompt => p_system)::text $$;
```

Test both:

```
SELECT vector_dims(legal.embed('test'));
SELECT legal.llm('Reply with exactly: HorizonDB AI test successful', 'You are a validation assistant.');
```

Expected result: 1536, then a short text reply.

Note (Option B, your own models): register your embedding model as my-embedding and your chat model under an alias, as in Day 1 Lab 2. Then change the function bodies to azure_openai.create_embeddings('my-embedding', p_text)::vector and add model => '<your chat alias>' to azure_ai.generate. Nothing else in Labs 5 to 7 changes. Check the exact argument names with your instructor, because preview signatures can change.

### Task 2: Create and load the document table

The library has three kinds of documents: published court opinions, firm research memos and privileged matter notes. The classification column is used in Lab 7.

```
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

Expected result: 12 rows inserted.

### Task 3: Generate embeddings

```
UPDATE legal.documents
SET embedding = legal.embed(title || '. ' || content)
WHERE embedding IS NULL;

SELECT COUNT(*) AS total_docs, COUNT(embedding) AS docs_with_embeddings
FROM legal.documents;
```

Expected result: 12 and 12. If the counts differ, check Task 1 and the model setup before you continue.

### Task 4: Build the citation graph

The graph holds only document IDs and CITES edges (an edge from A to B means A cites B). The relational table stays the source of truth for the text. Run the CREATE statement once, because a second run creates duplicates.

```
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
$$) AS (result agtype);
```

Verify the graph:

```
SELECT * FROM cypher('legal_graph', $$ MATCH (n) RETURN count(n) $$) AS (vertices agtype);
SELECT * FROM cypher('legal_graph', $$ MATCH ()-[r]->() RETURN count(r) $$) AS (edges agtype);
```

Expected result: 12 vertices and 20 edges.

Note: Every cypher() call needs an AS (...) clause with one agtype column for each returned value. If a statement fails with a cypher function error, check that age is preloaded (Exercise 0, Task 2).

Checkpoint: You have 12 embedded documents and a graph that records which document cites which.

## Exercise 2: Retrieve with vectors, then expand with the graph (15 minutes)

### Task 1: Vector search alone

```
SELECT doc_id, title,
       ROUND((embedding <=> legal.embed('Can a court narrow an overbroad non-compete instead of striking it down?'))::numeric, 4) AS distance
FROM legal.documents
ORDER BY distance
LIMIT 3;
```

Expected result: CASE-002 (Brightwater Logistics v. Harlan) is first or near the top. The case it builds on, CASE-001, and the later cases that apply it may rank lower or not appear, even though a complete answer needs them. This is the gap the graph fills.

### Task 2: Create the graph lookup functions

The first function runs the openCypher queries. AGE needs a literal query string, so the function builds the full statement with format() and runs it with EXECUTE. It checks the ID format first. It returns documents that the starting document cites and documents that cite it.

```
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

The second function adds titles from the relational table. It lists the documents that the starting document cites first (the authority it rests on), then the documents that cite it:

```
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

### Task 3: Test the graph expansion

```
SELECT * FROM legal.related_docs('CASE-002', 4);
```

Expected result: CASE-001 (cites), then CASE-004, CASE-005 and MEMO-002 (cited_by). A fifth neighbor, NOTE-001, is cut by the limit of 4. Brightwater rests on Alder and was applied by later cases and memos, and the graph shows that in one query.

### Task 4: Combine both steps in one function

The vector hit is the starting point, and the graph supplies the connected authority. No document ID is typed by hand.

```
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

Expected result: CASE-002 found by vector, then CASE-001, CASE-004 and CASE-005 found by graph. The text of the case, the authority it rests on, and the cases that applied it are now available as evidence.

### Task 5: Compare

Run the function again with: What is the reasonableness test for non-competes, and which later documents rely on it?

Answer these questions with your instructor:

1. Which document does the vector search find first, and which ones does the graph add?
2. Why is the text read from the relational table and not stored in the graph?
3. What would break if the starting document were wrong? (Retrieval quality depends on the vector step.)

Checkpoint: You have a SQL-only GraphRAG retrieval flow. Next, an agent chooses these steps for itself.

## Exercise 3: Build the legal research agent 

The agent has four tools. The model picks one at a time by replying with a small JSON message, the Python program runs the tool against HorizonDB, and the result goes back to the model. This uses only the in-database models from Exercise 1, so no extra model keys are needed.

| Tool | What it does |
|---|---|
| search_documents | Vector search: the 3 closest documents |
| find_related_documents | Citation graph expansion from one document (legal.related_docs) |
| get_document | Full text of one document |
| recall_memory | Recent messages from this session |

The model never receives SQL access. It can only name one of these four tools.

### Task 1: Create the memory table

```
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

### Task 2: Set up Python

In a terminal:

```
mkdir legal-agent
cd legal-agent
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "psycopg[binary]"
```

On Windows PowerShell, activate with .venv\Scripts\Activate.ps1. Then set the connection details. Replace the placeholders with your values and do not share the password.

```
export HORIZONDB_DSN='host=<CLUSTER_ENDPOINT> port=5432 dbname=legalai_lab user=lawadmin password=<PASSWORD> sslmode=require'
export AGENT_SESSION_ID='lab5-demo'
```

On Windows PowerShell, use $env:HORIZONDB_DSN = '...' and $env:AGENT_SESSION_ID = 'lab5-demo'.

### Task 3: Create agent.py

Create a file named agent.py with this content:

```python
import json
import os
import re
import uuid

import psycopg

DSN = os.environ['HORIZONDB_DSN']
SESSION_ID = os.getenv('AGENT_SESSION_ID', 'session-' + uuid.uuid4().hex[:8])
MAX_STEPS = 5
DOC_ID = re.compile('^(CASE|MEMO|NOTE)-[0-9]{3}$')
NL = chr(10)

TOOL_CATALOG = '''
1. search_documents - args: {"query": "<text>"}
   Semantic search. Returns the 3 closest documents.
2. find_related_documents - args: {"doc_id": "CASE-001"}
   Follows the citation graph: returns documents that the given document cites and documents that cite it.
3. get_document - args: {"doc_id": "CASE-001"}
   Returns the full text of one document.
4. recall_memory - args: {"limit": <number>}
   Returns the most recent messages from this session.
'''

SYSTEM_PROMPT = '''You are the Calder & Voss Legal Research Agent.
You answer legal research questions using ONLY text returned by your tools.

Tools:
''' + TOOL_CATALOG + '''
Reply with exactly ONE JSON object and nothing else, in one of these forms:
{"action": "tool", "tool": "<tool name>", "args": {}}
{"action": "answer", "answer": "<final answer>", "sources": ["CASE-001"]}

Rules:
- Start with search_documents for any research question.
- Use find_related_documents to trace the authority a case rests on and the documents that apply it.
- Use recall_memory when the user refers to earlier messages.
- Never invent case names, holdings, citations or years. If the tools do not contain the answer, say the information is not in the research library.
- Say whether each point comes from a court opinion (CASE), a firm memo (MEMO) or a matter note (NOTE).
- In the final answer, cite the document ID and title for each claim, and list the document IDs in sources.
'''

SEARCH_SQL = '''
WITH q AS (SELECT legal.embed(%s::text) AS v)
SELECT d.doc_id, d.title, d.doc_type, ROUND((d.embedding <=> q.v)::numeric, 4), LEFT(d.content, 160)
FROM legal.documents AS d, q
ORDER BY d.embedding <=> q.v
LIMIT 3
'''


def tool_search_documents(conn, args):
    query = str(args.get('query', '')).strip()
    if not query:
        return 'Error: query is required.'
    rows = conn.execute(SEARCH_SQL, (query,)).fetchall()
    lines = [f'{r[0]} | {r[1]} | {r[2]} | distance {r[3]} | {r[4]}...' for r in rows]
    return NL.join(lines) or 'No documents found.'


def tool_find_related(conn, args):
    doc_id = str(args.get('doc_id', '')).strip()
    if not DOC_ID.match(doc_id):
        return 'Error: doc_id must look like CASE-001, MEMO-001 or NOTE-001.'
    rows = conn.execute(
        'SELECT doc_id, title, relation FROM legal.related_docs(%s::text, 6)',
        (doc_id,),
    ).fetchall()
    meaning = {'cites': f'{doc_id} cites this document', 'cited_by': f'this document cites {doc_id}'}
    lines = [f'{r[0]} | {r[1]} | {meaning.get(r[2], r[2])}' for r in rows]
    return NL.join(lines) or 'No related documents found.'


def tool_get_document(conn, args):
    doc_id = str(args.get('doc_id', '')).strip()
    if not DOC_ID.match(doc_id):
        return 'Error: doc_id must look like CASE-001, MEMO-001 or NOTE-001.'
    row = conn.execute(
        'SELECT doc_id, title, doc_type, decision_year, content FROM legal.documents WHERE doc_id = %s',
        (doc_id,),
    ).fetchone()
    if row is None:
        return f'No document {doc_id} was found, or you do not have access to it.'
    return f'{row[0]} | {row[1]} | {row[2]} | {row[3]}' + NL + row[4]


def tool_recall_memory(conn, args):
    try:
        limit = max(1, min(int(args.get('limit', 6)), 20))
    except (TypeError, ValueError):
        limit = 6
    rows = conn.execute(
        '''SELECT role, content FROM (
               SELECT message_id, role, content FROM legal.agent_messages
               WHERE session_id = %s AND role IN ('user', 'assistant')
               ORDER BY message_id DESC LIMIT %s) AS recent
           ORDER BY message_id''',
        (SESSION_ID, limit),
    ).fetchall()
    return NL.join(f'{r[0]}: {r[1]}' for r in rows) or 'No earlier messages.'


TOOLS = {
    'search_documents': tool_search_documents,
    'find_related_documents': tool_find_related,
    'get_document': tool_get_document,
    'recall_memory': tool_recall_memory,
}


def log(conn, role, content):
    conn.execute(
        'INSERT INTO legal.agent_messages (session_id, role, content) VALUES (%s, %s, %s)',
        (SESSION_ID, role, content),
    )


def ask_model(conn, prompt):
    return conn.execute('SELECT legal.llm(%s::text, %s::text)', (prompt, SYSTEM_PROMPT)).fetchone()[0]


def parse_json(text):
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        raise ValueError('no JSON object found')
    return json.loads(text[start:end + 1])


def ask(conn, question):
    log(conn, 'user', question)
    scratchpad = []
    for step in range(1, MAX_STEPS + 1):
        prompt = ('QUESTION:' + NL + question + NL + NL + 'TOOL RESULTS SO FAR:' + NL
                  + (NL + NL).join(scratchpad or ['(none yet)'])
                  + NL + NL + 'Reply with one JSON object.')
        try:
            decision = parse_json(ask_model(conn, prompt))
        except (ValueError, json.JSONDecodeError):
            scratchpad.append('SYSTEM: your last reply was not valid JSON. Reply with one JSON object only.')
            continue
        if decision.get('action') == 'answer':
            answer = str(decision.get('answer', '')).strip()
            log(conn, 'assistant', answer)
            return answer, decision.get('sources', [])
        name = decision.get('tool')
        args = decision.get('args')
        args = args if isinstance(args, dict) else {}
        tool = TOOLS.get(name)
        if tool is None:
            result = f'Error: unknown tool {name}.'
        else:
            try:
                result = tool(conn, args)
            except Exception as exc:
                result = f'Error running {name}: {exc}'
        print(f'  [step {step}] tool={name} args={json.dumps(args)}')
        log(conn, 'tool', f'{name}({json.dumps(args)}) -> {result}')
        scratchpad.append(f'TOOL {name} {json.dumps(args)} RESULT:' + NL + result)
    message = 'I could not finish this request within the step limit.'
    log(conn, 'assistant', message)
    return message, []


def main():
    with psycopg.connect(DSN, autocommit=True) as conn:
        earlier = conn.execute(
            'SELECT COUNT(*) FROM legal.agent_messages WHERE session_id = %s', (SESSION_ID,)
        ).fetchone()[0]
        print(f'Session {SESSION_ID} has {earlier} earlier messages. Type exit to quit.')
        while True:
            question = input(NL + 'You: ').strip()
            if question.lower() in ('exit', 'quit'):
                break
            if not question:
                continue
            answer, sources = ask(conn, question)
            print(NL + 'Agent: ' + answer)
            print('Sources: ' + (', '.join(sources) or 'none'))


if __name__ == '__main__':
    main()
```

### Task 4: Run the agent

Run python agent.py and ask these questions one at a time. Watch the [step] lines, because they show which tool the model chose.

| Test | Question | What you should see |
|---|---|---|
| 1 | Can a court narrow an overbroad non-compete instead of striking it down? | search_documents, then find_related_documents for CASE-002. The answer says yes, citing Brightwater (CASE-002), the Alder test it rests on (CASE-001), and later documents that applied it (for example CASE-005 and MEMO-002). |
| 2 | What is the reasonableness test for non-competes, and which later documents rely on it? | CASE-001 (three parts: duration, geographic area, scope of activity), then the documents that cite it (CASE-002, CASE-003, MEMO-001). |
| 3 | What did I ask you first in this session? | recall_memory, then the first question from this session. |
| 4 | Is a non-compete in the sale of a business treated differently from one in employment? | CASE-003: judged more leniently, and a five-year restriction was upheld. |
| 5 | What is the law on cryptocurrency taxation? | The agent says the information is not in the research library and does not invent an answer. |

The wording of answers varies between runs. Judge the tools used, the documents retrieved and the citations, not the exact sentences. If the model replies with text that is not JSON, the program asks it to try again, up to five steps.

Note: Your agent may quote matter notes (NOTE-) in its answers, because you are connected as the administrator. Those notes are privileged client advice. Keep this in mind for Lab 7.

### Task 5: Check the persistent memory

Enter exit, then run in SQL:

```
SELECT message_id, role, LEFT(content, 100) AS content_start
FROM legal.agent_messages
WHERE session_id = 'lab5-demo'
ORDER BY message_id;
```

Expected result: your questions (user), each tool result (tool) and the answers (assistant). Restart python agent.py with the same AGENT_SESSION_ID, ask What did I ask you first in this session?, and confirm that the agent still remembers it.

Note: This is conversation memory. The agent recalls recent messages but does not learn lasting facts about the user.

Checkpoint: You have a working GraphRAG agent whose tools, memory and audit trail all live in HorizonDB.

