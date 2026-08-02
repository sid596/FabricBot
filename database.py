import sqlite3

DB_NAME = "fabricbot.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS conversations (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        phone TEXT UNIQUE,

        goal TEXT,

        status TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    conn.commit()
    conn.close()


def get_or_create_conversation(phone):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM conversations WHERE phone=?",
        (phone,)
    )

    row = cur.fetchone()

    if row:

        conn.close()
        return dict(row)

    cur.execute(
        """
        INSERT INTO conversations
        (phone,status)

        VALUES (?,?)
        """,
        (phone, "active")
    )

    conn.commit()

    conversation_id = cur.lastrowid

    conn.close()

    return {

        "id": conversation_id,

        "phone": phone,

        "status": "active"

    }