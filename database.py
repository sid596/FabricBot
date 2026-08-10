import sqlite3
from conversation import ConversationState
from pathlib import Path

DB_NAME = str(Path(__file__).resolve().parent / "fabricbot.db")


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

        state TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    conn.commit()
    conn.close()



def get_conversation(phone):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT state FROM conversations WHERE phone=?",
        (phone,),
    )

    row = cur.fetchone()

    if row:
        conn.close()
        return ConversationState.from_json(row["state"])

    state = ConversationState()

    cur.execute(
        """
        INSERT INTO conversations(phone,state)
        VALUES(?,?)
        """,
        (
            phone,
            state.to_json(),
        ),
    )

    conn.commit()
    conn.close()

    return state




def save_conversation(phone, state):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute("""

    INSERT INTO conversations(phone,state)

    VALUES(?,?)

    ON CONFLICT(phone)

    DO UPDATE SET

        state=?,

        updated_at=CURRENT_TIMESTAMP

    """,

    (

        phone,

        state.to_json(),

        state.to_json()

    )

    )

    conn.commit()

    conn.close()


