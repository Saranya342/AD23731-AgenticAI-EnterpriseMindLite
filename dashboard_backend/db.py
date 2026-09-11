# """
# Database helper for the dashboard backend.

# Reuses the SAME DATABASE_URL already set up for the rest of the project
# (reads it from the .env file one folder up, at the project root) —
# does not introduce a second database or new credentials.
# """

# import os
# import psycopg2
# import psycopg2.extras
# from dotenv import load_dotenv

# load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# DATABASE_URL = os.getenv("DATABASE_URL")

# if not DATABASE_URL:
#     raise ValueError("Missing environment variable: DATABASE_URL")


# def get_connection():
#     return psycopg2.connect(DATABASE_URL)


# def fetch_all(query, params=None):
#     conn = get_connection()
#     try:
#         cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#         cur.execute(query, params or ())
#         rows = cur.fetchall()
#         cur.close()
#         return [dict(r) for r in rows]
#     finally:
#         conn.close()


# def fetch_one(query, params=None):
#     conn = get_connection()
#     try:
#         cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#         cur.execute(query, params or ())
#         row = cur.fetchone()
#         cur.close()
#         return dict(row) if row else None
#     finally:
#         conn.close()
"""
Database helper for the dashboard backend.

Reuses the SAME DATABASE_URL already configured for the project.
Adds connection and query timeouts so API requests do not hang forever.
"""

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv


# Load .env from project root
load_dotenv(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".env"
    )
)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("Missing environment variable: DATABASE_URL")


# ---------------------------------------------------------
# Database connection
# ---------------------------------------------------------

def get_connection():
    """
    Create a PostgreSQL connection with a timeout.

    connect_timeout prevents the API from hanging indefinitely
    when PostgreSQL/Supabase cannot be reached.
    """

    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=10,
    )


# ---------------------------------------------------------
# Fetch multiple rows
# ---------------------------------------------------------

def fetch_all(query, params=None):
    """
    Execute a SELECT query and return all rows as dictionaries.
    """

    conn = get_connection()

    try:
        cur = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        # Prevent a SQL query from running forever.
        cur.execute("SET statement_timeout = 15000")

        cur.execute(query, params or ())

        rows = cur.fetchall()

        cur.close()

        return [dict(row) for row in rows]

    finally:
        conn.close()


# ---------------------------------------------------------
# Fetch one row
# ---------------------------------------------------------

def fetch_one(query, params=None):
    """
    Execute a SELECT query and return one row as a dictionary.
    """

    conn = get_connection()

    try:
        cur = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        # Prevent a SQL query from running forever.
        cur.execute("SET statement_timeout = 15000")

        cur.execute(query, params or ())

        row = cur.fetchone()

        cur.close()

        return dict(row) if row else None

    finally:
        conn.close()