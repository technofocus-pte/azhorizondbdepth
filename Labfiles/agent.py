import json

import os

import re

import uuid



import psycopg





# ============================================================

# 1. Configuration

# ============================================================



DSN = os.environ["HORIZONDB_DSN"]



SESSION_ID = os.getenv(

    "AGENT_SESSION_ID",

    "session-" + uuid.uuid4().hex[:8]

)



MAX_STEPS = 10

DEBUG = False



DOC_ID = re.compile(r"^(CASE|MEMO|NOTE)-[0-9]{3}$")

NL = chr(10)





# ============================================================

# 2. Tool catalog

# ============================================================



TOOL_CATALOG = """1. search_documents - args: {"query": "<text>"}

   Semantic search. Returns the 3 closest documents.



2. find_related_documents - args: {"doc_id": "CASE-001"}

   Follows the citation graph: returns documents that the

   given document cites and documents that cite it.



3. get_document - args: {"doc_id": "CASE-001"}

   Returns the full text of one document.



4. recall_memory - args: {"limit": <number>}

   Returns the most recent messages from this session."""





# ============================================================

# 3. System prompt

# ============================================================



SYSTEM_PROMPT = """You are the Calder & Voss Legal Research Agent.



You answer legal research questions using ONLY text returned

by your tools.



Available tools:

""" + TOOL_CATALOG + """



You MUST return exactly ONE valid JSON object.



There are only two permitted response formats.



TOOL CALL:

{"action":"tool","tool":"search_documents","args":{"query":"search terms"}}



FINAL ANSWER:

{"action":"answer","answer":"Your answer here","sources":["CASE-001"]}



IMPORTANT RULES:



1. Start with search_documents for every research question.

2. Use find_related_documents to trace the authority a case

   rests on and identify documents that apply it.

3. Use get_document to retrieve the full text of relevant

   documents before making detailed legal claims.

4. Use recall_memory when the user refers to earlier messages.

5. Never invent case names, holdings, citations or years.

6. Use ONLY information returned by the tools.

7. If the tools do not contain the answer, say the information

   is not in the research library.

8. Identify whether each point comes from a court opinion

   (CASE), a firm memo (MEMO), or a matter note (NOTE).

9. Cite the document ID and title for each claim.

10. List the supporting document IDs in the sources array.

11. Do not cite irrelevant documents.

12. If no retrieved document supports the answer, use an

    empty sources array.



STRICT JSON OUTPUT REQUIREMENTS:



- Return raw JSON with no code fences.

- Do not write natural-language text outside JSON.

- Do not add introductory or concluding text outside JSON.

- Use double quotes for all JSON keys and string values.

- Escape newline characters inside JSON string values.

- Do not use trailing commas.

- Do not return incomplete JSON.

- Do not repeat the user's question as an answer.

- If a tool result contains enough information, return a final answer.

- Keep the final answer concise enough to fit in one response.



Every response must start with { and end with }."""





# ============================================================

# 4. Semantic search SQL

# ============================================================



SEARCH_SQL = """

WITH q AS (

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

LIMIT 3

"""





# ============================================================

# 5. Tool: Search documents

# ============================================================



def tool_search_documents(conn, args):

    query = str(args.get("query", "")).strip()



    if not query:

        return "Error: query is required."



    rows = conn.execute(

        SEARCH_SQL,

        (query,)

    ).fetchall()



    lines = [

        f"{r[0]} | {r[1]} | {r[2]} | distance {r[3]} | {r[4]}..."

        for r in rows

    ]



    return NL.join(lines) or "No documents found."





# ============================================================

# 6. Tool: Find related documents

# ============================================================



def tool_find_related(conn, args):

    doc_id = str(args.get("doc_id", "")).strip()



    if not DOC_ID.match(doc_id):

        return (

            "Error: doc_id must look like "

            "CASE-001, MEMO-001 or NOTE-001."

        )



    rows = conn.execute(

        """

        SELECT doc_id, title, relation

        FROM legal.related_docs(%s::text, 6)

        """,

        (doc_id,)

    ).fetchall()



    meaning = {

        "cites": f"{doc_id} cites this document",

        "cited_by": f"this document cites {doc_id}"

    }



    lines = [

        f"{r[0]} | {r[1]} | {meaning.get(r[2], r[2])}"

        for r in rows

    ]



    return NL.join(lines) or "No related documents found."





# ============================================================

# 7. Tool: Get full document

# ============================================================



def tool_get_document(conn, args):

    doc_id = str(args.get("doc_id", "")).strip()



    if not DOC_ID.match(doc_id):

        return (

            "Error: doc_id must look like "

            "CASE-001, MEMO-001 or NOTE-001."

        )



    row = conn.execute(

        """

        SELECT

            doc_id,

            title,

            doc_type,

            decision_year,

            content

        FROM legal.documents

        WHERE doc_id = %s

        """,

        (doc_id,)

    ).fetchone()



    if row is None:

        return (

            f"No document {doc_id} was found, "

            "or you do not have access to it."

        )



    return (

        f"{row[0]} | {row[1]} | {row[2]} | {row[3]}"

        + NL

        + row[4]

    )





# ============================================================

# 8. Tool: Recall conversation memory

# ============================================================



def tool_recall_memory(conn, args):

    try:

        limit = max(

            1,

            min(int(args.get("limit", 6)), 20)

        )

    except (TypeError, ValueError):

        limit = 6



    rows = conn.execute(

        """

        SELECT role, content

        FROM (

            SELECT message_id, role, content

            FROM legal.agent_messages

            WHERE session_id = %s

              AND role IN ('user', 'assistant')

            ORDER BY message_id DESC

            LIMIT %s

        ) AS recent

        ORDER BY message_id

        """,

        (SESSION_ID, limit)

    ).fetchall()



    return (

        NL.join(f"{r[0]}: {r[1]}" for r in rows)

        or "No earlier messages."

    )





# ============================================================

# 9. Register available tools

# ============================================================



TOOLS = {

    "search_documents": tool_search_documents,

    "find_related_documents": tool_find_related,

    "get_document": tool_get_document,

    "recall_memory": tool_recall_memory,

}



TOOL_LABELS = {

    "search_documents": "Searching documents",

    "find_related_documents": "Tracing related authorities",

    "get_document": "Retrieving full document",

    "recall_memory": "Checking conversation memory",

}





# ============================================================

# 10. Conversation logging

# ============================================================



def log(conn, role, content):

    conn.execute(

        """

        INSERT INTO legal.agent_messages

            (session_id, role, content)

        VALUES (%s, %s, %s)

        """,

        (SESSION_ID, role, content)

    )





# ============================================================

# 11. Call HorizonDB language model

# ============================================================



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





# ============================================================

# 12. Parse model JSON response

# ============================================================



def parse_json(response):

    if not isinstance(response, str):

        raise ValueError(

            f"Expected string response, got "

            f"{type(response).__name__}"

        )



    response = response.strip()



    if not response:

        raise ValueError("Model returned an empty response.")



    # Remove Markdown code fences.

    response = re.sub(

        r"^\s*```(?:json)?\s*",

        "",

        response,

        flags=re.IGNORECASE

    )



    response = re.sub(

        r"\s*```\s*$",

        "",

        response

    )



    start = response.find("{")



    if start == -1:

        raise ValueError("No JSON object found.")



    decoder = json.JSONDecoder()



    try:

        decision, end = decoder.raw_decode(

            response[start:]

        )

    except json.JSONDecodeError as exc:

        raise ValueError(

            f"Invalid JSON: {exc}"

        ) from exc



    if not isinstance(decision, dict):

        raise ValueError(

            "JSON response must be an object."

        )



    if decision.get("action") not in ("tool", "answer"):

        raise ValueError(

            "JSON response has an invalid action."

        )



    return decision





# ============================================================

# 13. Validate final answer

# ============================================================



def validate_final_answer(decision):

    answer = decision.get("answer")



    if not isinstance(answer, str) or not answer.strip():

        raise ValueError(

            "Final answer is missing or empty."

        )



    sources = decision.get("sources", [])



    if not isinstance(sources, list):

        sources = []



    # Retain only correctly formatted document IDs.

    sources = [

        str(source)

        for source in sources

        if DOC_ID.match(str(source))

    ]



    return answer.strip(), sources





# ============================================================

# 14. Short tool status messages

# ============================================================



def get_tool_summary(name, result):

    result = str(result)



    if result.startswith("Error"):

        return result



    if name == "search_documents":

        if result == "No documents found.":

            return "No matching documents found."



        count = len(result.splitlines())

        return f"Retrieved {count} document(s)."



    if name == "find_related_documents":

        if result == "No related documents found.":

            return "No related documents found."



        count = len(result.splitlines())

        return f"Found {count} related document(s)."



    if name == "get_document":

        if result.startswith("No document"):

            return result



        return "Full document retrieved."



    if name == "recall_memory":

        if result == "No earlier messages.":

            return result



        return "Conversation history retrieved."



    return "Tool completed."





# ============================================================

# 15. Main agent execution loop

# ============================================================



def ask(conn, question):

    log(conn, "user", question)



    scratchpad = []



    for step in range(1, MAX_STEPS + 1):



        prompt = (

            "QUESTION:"

            + NL

            + question

            + NL

            + NL

            + "TOOL RESULTS SO FAR:"

            + NL

            + (NL + NL).join(

                scratchpad or ["(none yet)"]

            )

            + NL

            + NL

            + "Reply with exactly one valid JSON object."

            + NL

            + "Do not answer outside JSON."

        )



        # ----------------------------------------------------

        # Call model

        # ----------------------------------------------------



        try:

            raw_response = ask_model(

                conn,

                prompt

            )



            raw_text = str(raw_response)



            if DEBUG:

                print("\n[DEBUG] Raw model response:")

                print(raw_text)



        except Exception as exc:

            print(

                f"\nModel call failed: "

                f"{type(exc).__name__}: {exc}"

            )



            scratchpad.append(

                f"SYSTEM: Model call failed: {exc}"

            )



            continue



        # ----------------------------------------------------

        # Parse JSON

        # ----------------------------------------------------



        try:

            decision = parse_json(raw_text)



            if DEBUG:

                print("\n[DEBUG] Parsed decision:")

                print(

                    json.dumps(

                        decision,

                        indent=2,

                        ensure_ascii=False

                    )

                )



        except ValueError as exc:

            if DEBUG:

                print(f"\n[DEBUG] JSON parsing error: {exc}")



            scratchpad.append(

                "SYSTEM: Your previous response did not follow "

                "the required JSON format. Return exactly one "

                "valid JSON object. Do not return natural language "

                "outside JSON. Do not repeat the previous response."

            )



            continue



        # ----------------------------------------------------

        # Process final answer

        # ----------------------------------------------------



        if decision["action"] == "answer":



            try:

                answer, sources = validate_final_answer(

                    decision

                )



            except ValueError as exc:

                if DEBUG:

                    print(

                        f"\n[DEBUG] Answer validation error: {exc}"

                    )



                scratchpad.append(

                    "SYSTEM: Return a non-empty final answer "

                    "in the required JSON format."

                )



                continue



            log(

                conn,

                "assistant",

                answer

            )



            return answer, sources



        # ----------------------------------------------------

        # Process tool request

        # ----------------------------------------------------



        name = decision.get("tool")

        args = decision.get("args")



        if not isinstance(args, dict):

            args = {}



        tool = TOOLS.get(name)



        # Display only a short status message.

        label = TOOL_LABELS.get(

            name,

            "Running research tool"

        )



        print(f"  {label}...", flush=True)



        if DEBUG:

            print(

                f"[DEBUG] Tool: {name}"

            )

            print(

                "[DEBUG] Arguments:",

                json.dumps(args, ensure_ascii=False)

            )



        if tool is None:

            result = f"Error: unknown tool {name}."



        else:

            try:

                result = tool(

                    conn,

                    args

                )



            except Exception as exc:

                result = (

                    f"Error running {name}: "

                    f"{type(exc).__name__}: {exc}"

                )



        result_text = str(result)



        # Show a short summary instead of the full result.

        print(

            f"  {get_tool_summary(name, result_text)}"

        )



        if DEBUG:

            print("\n[DEBUG] Full tool result:")

            print(result_text)



        # ----------------------------------------------------

        # Log tool execution

        # ----------------------------------------------------



        tool_log = (

            f"{name}("

            + json.dumps(args, ensure_ascii=False)

            + f") -> {result_text}"

        )



        log(

            conn,

            "tool",

            tool_log

        )



        scratchpad.append(

            f"TOOL {name} "

            + json.dumps(args, ensure_ascii=False)

            + " RESULT:"

            + NL

            + result_text

        )



    # ========================================================

    # Maximum step limit reached

    # ========================================================



    message = (

        "I could not finish this request within the step limit. "

        "Please try again."

    )



    print(

        f"\nResearch stopped: maximum of {MAX_STEPS} steps reached."

    )



    log(

        conn,

        "assistant",

        message

    )



    return message, []





# ============================================================

# 16. Main application

# ============================================================



def main():



    with psycopg.connect(

        DSN,

        autocommit=True

    ) as conn:



        earlier = conn.execute(

            """

            SELECT COUNT(*)

            FROM legal.agent_messages

            WHERE session_id = %s

            """,

            (SESSION_ID,)

        ).fetchone()[0]



        if earlier:

            print(

                f"Session {SESSION_ID} is ready "

                f"({earlier} earlier messages)."

            )

        else:

            print(

                f"Session {SESSION_ID} is ready."

            )



        print("Type exit to quit.")



        while True:



            try:

                question = input(

                    NL + "You: "

                ).strip()



            except (EOFError, KeyboardInterrupt):

                print("\nExiting agent.")

                break



            if question.lower() in ("exit", "quit"):

                print("Goodbye.")

                break



            if not question:

                continue



            try:

                answer, sources = ask(

                    conn,

                    question

                )



                print("\nAgent")

                print("-" * 60)

                print(answer)



                if sources:

                    print(

                        "\nSources: " + ", ".join(sources)

                    )



                print("-" * 60)



            except Exception as exc:

                print(

                    f"\nApplication error: "

                    f"{type(exc).__name__}: {exc}"

                )





# ============================================================

# 17. Entry point

# ============================================================



if __name__ == "__main__":

    main()
