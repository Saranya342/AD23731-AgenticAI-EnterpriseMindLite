import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from dashboard_backend.db import (
    fetch_all,
    execute_query,
)


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "Missing GEMINI_API_KEY in .env"
    )


client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# GENERATE EMBEDDING
# ============================================================

def generate_embedding(text):

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=768
        ),
    )

    return result.embeddings[0].values


# ============================================================
# CONVERT EMBEDDING TO POSTGRES VECTOR FORMAT
# ============================================================

def embedding_to_vector(embedding):

    return (
        "["
        + ",".join(
            str(value)
            for value in embedding
        )
        + "]"
    )


# ============================================================
# GENERATE EMBEDDINGS FOR NEW KNOWLEDGE
# ============================================================

def generate_sop_embeddings():

    rows = fetch_all(
        """
        SELECT
            id,
            title,
            service,
            content
        FROM knowledge_base
        WHERE embedding IS NULL
        ORDER BY id;
        """
    )

    print(
        f"[RAG] Documents without embeddings: "
        f"{len(rows)}"
    )

    for row in rows:

        print(
            f"[RAG] Generating embedding for: "
            f"{row['title']}"
        )

        text = f"""
Title: {row['title']}

Service: {row['service']}

Content:
{row['content']}
""".strip()

        embedding = generate_embedding(
            text
        )

        vector_string = embedding_to_vector(
            embedding
        )

        execute_query(
            """
            UPDATE knowledge_base
            SET embedding = %s::vector
            WHERE id = %s;
            """,
            (
                vector_string,
                row["id"],
            ),
        )

        print(
            f"[RAG] Saved embedding for ID "
            f"{row['id']}"
        )

    print()
    print(
        "[RAG] Embedding generation completed."
    )


# ============================================================
# RETRIEVE RELEVANT KNOWLEDGE
# ============================================================

def retrieve_relevant_knowledge(
    query_text,
    limit=3,
    service=None
):

    print()
    print(
        "[RAG] Searching relevant knowledge..."
    )

    # --------------------------------------------------------
    # Show service filter
    # --------------------------------------------------------

    if service:

        print(
            f"[RAG] Service filter: {service}"
        )

    # --------------------------------------------------------
    # Generate embedding for current incident
    # --------------------------------------------------------

    query_embedding = generate_embedding(
        query_text
    )

    vector_string = embedding_to_vector(
        query_embedding
    )

    # --------------------------------------------------------
    # SERVICE-SPECIFIC RETRIEVAL
    #
    # If Agent 2 already knows the affected service,
    # search only knowledge belonging to that service.
    # --------------------------------------------------------

    if service:

        service_rows = fetch_all(
            """
            SELECT
                id,
                document_type,
                title,
                service,
                content,

                1 - (
                    embedding <=> %s::vector
                ) AS similarity

            FROM knowledge_base

            WHERE embedding IS NOT NULL

              AND LOWER(TRIM(service))
                  = LOWER(TRIM(%s))

            ORDER BY
                embedding <=> %s::vector

            LIMIT %s;
            """,
            (
                vector_string,
                service,
                vector_string,
                limit,
            ),
        )

        # ----------------------------------------------------
        # If matching service knowledge exists,
        # return ONLY those documents.
        # ----------------------------------------------------

        if service_rows:

            print(
                f"[RAG] Found "
                f"{len(service_rows)} "
                f"service-specific document(s)."
            )

            return service_rows

        # ----------------------------------------------------
        # No SOP exists for that service.
        # Fall back to global semantic search.
        # ----------------------------------------------------

        print(
            "[RAG] No knowledge found for "
            f"service '{service}'."
        )

        print(
            "[RAG] Falling back to "
            "general similarity search."
        )

    # --------------------------------------------------------
    # GENERAL VECTOR SEARCH
    #
    # Used when:
    # 1. service is unknown
    # 2. no service-specific SOP exists
    # --------------------------------------------------------

    rows = fetch_all(
        """
        SELECT
            id,
            document_type,
            title,
            service,
            content,

            1 - (
                embedding <=> %s::vector
            ) AS similarity

        FROM knowledge_base

        WHERE embedding IS NOT NULL

        ORDER BY
            embedding <=> %s::vector

        LIMIT %s;
        """,
        (
            vector_string,
            vector_string,
            limit,
        ),
    )

    return rows


# ============================================================
# TEST RAG
# ============================================================

def test_rag():

    test_incident = """
ABC Retail is experiencing intermittent
Payment Gateway timeout errors during checkout.

Several payment transactions are failing
and customers have to retry their payments.
""".strip()

    print()
    print("=" * 70)
    print("[RAG] TEST INCIDENT")
    print("=" * 70)

    print(
        test_incident
    )

    results = retrieve_relevant_knowledge(
        query_text=test_incident,
        limit=3,
        service="Payment Gateway"
    )

    print()
    print("=" * 70)
    print("[RAG] RETRIEVED KNOWLEDGE")
    print("=" * 70)

    if not results:

        print(
            "[RAG] No relevant knowledge found."
        )

        return

    for index, item in enumerate(
        results,
        start=1
    ):

        print()
        print(
            f"Result #{index}"
        )

        print(
            "-" * 70
        )

        print(
            "Title:",
            item["title"]
        )

        print(
            "Document Type:",
            item["document_type"]
        )

        print(
            "Service:",
            item["service"]
        )

        similarity = item.get(
            "similarity"
        )

        if similarity is not None:

            print(
                "Similarity:",
                round(
                    float(similarity),
                    4
                )
            )

        print()

        print(
            "Content:"
        )

        print(
            item["content"]
        )

    print()
    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # Your existing SOPs already have embeddings.
    #
    # Leave this commented.
    #
    # When you add NEW SOPs later,
    # temporarily uncomment it and run this file.
    # --------------------------------------------------------

    # generate_sop_embeddings()

    # --------------------------------------------------------
    # Test service-aware RAG retrieval
    # --------------------------------------------------------

    test_rag()