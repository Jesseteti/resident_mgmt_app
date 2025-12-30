import os, bcrypt
from pathlib import Path
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set.\n"
            "Put it in .env or set it in PowerShell like:\n"
            '$env:DATABASE_URL="postgresql://..."'
        )
    return psycopg.connect(database_url, row_factory=dict_row)

def init_db():
    """
    Apply schema.sql to the current database.
    Run manually when you intend to create/reset schema.
    """
    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text(encoding="utf-8")

    with get_db_connection() as conn:
        conn.execute(sql)

def get_residents_with_balances():
    """
    Returns residents plus computed balance:
      charge increases balance
      payment decreases balance
      adjustment adds (positive adjustment increases balance; use carefully)
    """
    with get_db_connection() as conn:
        return conn.execute("""
            SELECT
                r.*,
                COALESCE(SUM(
                    CASE
                        WHEN le.entry_type = 'charge' THEN le.amount
                        WHEN le.entry_type = 'payment' THEN -le.amount
                        WHEN le.entry_type = 'adjustment' THEN le.amount
                        ELSE 0
                    END
                ), 0) AS balance
            FROM residents r
            LEFT JOIN ledger_entries le ON le.resident_id = r.id
            GROUP BY r.id
            ORDER BY
                CASE WHEN r.status = 'Active' THEN 0 ELSE 1 END,
                r.full_name ASC;
        """).fetchall()

def ensure_rent_charges_up_to_date(resident_id: int, today: date | None = None) -> int:
    """
    Insert missing automatic rent 'charge' entries up to today.

    Rules:
      - Weekly: every 7 days from start_date (start_date itself is first due date)
      - Monthly: on the 1st of the NEXT month after start_date, then every 1st

    Integrity:
      - pg_advisory_xact_lock(resident_id) prevents concurrent double-generation
      - unique index + ON CONFLICT DO NOTHING prevents duplicates
      - marks auto charges with source='auto_rent'
    """
    if today is None:
        today = date.today()

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Lock per resident for the duration of the transaction (prevents race conditions)
        cur.execute("SELECT pg_advisory_xact_lock(%s);", (resident_id,))

        # Load resident info
        cur.execute("""
            SELECT id, rate_amount, rate_frequency, start_date, status
            FROM residents
            WHERE id = %s;
        """, (resident_id,))
        r = cur.fetchone()
        if not r or r["status"] != "Active":
            conn.commit()
            return 0

        rate_amount = r["rate_amount"]
        freq = r["rate_frequency"]
        start_date = r["start_date"]  # DATE -> python date

        # Last auto rent charge date
        cur.execute("""
            SELECT MAX(entry_date) AS last_date
            FROM ledger_entries
            WHERE resident_id = %s
              AND entry_type = 'charge'
              AND source = 'auto_rent';
        """, (resident_id,))
        last = cur.fetchone()["last_date"]

        inserted = 0

        def insert_auto_rent(due_date: date):
            nonlocal inserted
            cur.execute("""
                INSERT INTO ledger_entries
                    (resident_id, entry_date, entry_type, amount, description, source)
                VALUES
                    (%s, %s, 'charge', %s, 'Auto rent charge', 'auto_rent')
                ON CONFLICT DO NOTHING;
            """, (resident_id, due_date, rate_amount))
            if cur.rowcount == 1:
                inserted += 1

        if freq == "Weekly":
            next_due = (last + timedelta(days=7)) if last else start_date
            while next_due <= today:
                insert_auto_rent(next_due)
                next_due += timedelta(days=7)

        elif freq == "Monthly":
            def first_of_next_month(d: date) -> date:
                if d.month == 12:
                    return date(d.year + 1, 1, 1)
                return date(d.year, d.month + 1, 1)

            # Monthly: first charge is next 1st after move-in
            next_due = first_of_next_month(last) if last else first_of_next_month(start_date)
            while next_due <= today:
                insert_auto_rent(next_due)
                next_due = first_of_next_month(next_due)

        else:
            raise ValueError(f"Unknown rate_frequency: {freq}")

        conn.commit()
        return inserted

    finally:
        conn.close()

def refresh_auto_charges_for_active_residents() -> int:
    """
    Brings all ACTIVE residents up to date on automatic rent charges.
    Safe to call repeatedly.
    Returns total number of new charges inserted across all residents.
    """
    with get_db_connection() as conn:
        ids = [row["id"] for row in conn.execute(
            "SELECT id FROM residents WHERE status = 'Active';"
        ).fetchall()]

    total = 0
    for rid in ids:
        total += ensure_rent_charges_up_to_date(rid)
    return total

def create_user(username: str, password: str, role: str = "staff") -> int:
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    with get_db_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, %s)
            RETURNING id;
            """,
            (username, pw_hash, role),
        ).fetchone()
        return row["id"]

def get_user_row_by_username(username: str):
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = %s;", (username,)
        ).fetchone()

def get_all_payments():
    with get_db_connection() as conn:
        return conn.execute(
            """
            SELECT
                le.id,
                le.entry_date,
                le.amount,
                le.description,
                r.full_name AS resident_name,
                rc.object_path AS receipt_object_path
            FROM ledger_entries le
            JOIN residents r ON r.id = le.resident_id
            LEFT JOIN receipts rc ON rc.ledger_entry_id = le.id
            WHERE le.entry_type = 'payment'
            ORDER BY le.entry_date DESC, le.id DESC;
            """
        ).fetchall()

def get_most_recent_payments(active_only: bool = True):

    status_filter = "AND r.status = 'Active'" if active_only else ""

    with get_db_connection() as conn:
        return conn.execute(
            f"""
            SELECT
                r.id,
                r.full_name,
                r.status,

                -- current balance
                COALESCE(SUM(
                    CASE
                        WHEN le.entry_type = 'charge' THEN le.amount
                        WHEN le.entry_type = 'payment' THEN -le.amount
                        WHEN le.entry_type = 'adjustment' THEN le.amount
                        ELSE 0
                    END
                ), 0) AS balance,

                -- most recent payment info
                p.entry_date AS last_payment_date,
                p.amount     AS last_payment_amount

            FROM residents r

            -- balance ledger join
            LEFT JOIN ledger_entries le
                ON le.resident_id = r.id

            -- most recent payment per resident
            LEFT JOIN LATERAL (
                SELECT entry_date, amount
                FROM ledger_entries
                WHERE resident_id = r.id
                  AND entry_type = 'payment'
                ORDER BY entry_date DESC, id DESC
                LIMIT 1
            ) p ON true

            WHERE 1 = 1
            {status_filter}

            GROUP BY
                r.id,
                r.full_name,
                r.status,
                p.entry_date,
                p.amount

            ORDER BY r.full_name ASC;
            """
        ).fetchall()


def insert_receipt_record(
    ledger_entry_id: int,
    resident_id: int,
    bucket: str,
    object_path: str,
    original_filename: str,
    content_type: str,
    file_size_bytes: int,
    sha256: str,
    created_by_user_id: int | None,
    cur=None,  # <-- optional cursor for same-transaction inserts
):
    sql = """
        INSERT INTO receipts
          (ledger_entry_id, resident_id, bucket, object_path, original_filename,
           content_type, file_size_bytes, sha256, created_by_user_id)
        VALUES
          (%s, %s, %s, %s, %s,
           %s, %s, %s, %s)
        ON CONFLICT (ledger_entry_id)
        DO UPDATE SET
          bucket = EXCLUDED.bucket,
          object_path = EXCLUDED.object_path,
          original_filename = EXCLUDED.original_filename,
          content_type = EXCLUDED.content_type,
          file_size_bytes = EXCLUDED.file_size_bytes,
          sha256 = EXCLUDED.sha256,
          created_by_user_id = EXCLUDED.created_by_user_id,
          created_at = now();
    """

    params = (
        ledger_entry_id,
        resident_id,
        bucket,
        object_path,
        original_filename,
        content_type,
        file_size_bytes,
        sha256,
        created_by_user_id,
    )

    # If caller provided a cursor, use it (same transaction)
    if cur is not None:
        cur.execute(sql, params)
        return

    # Otherwise open our own connection (standalone usage)
    with get_db_connection() as conn:
        conn.execute(sql, params)

def get_receipt_by_ledger_entry_id(ledger_entry_id: int):
    with get_db_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM receipts
            WHERE ledger_entry_id = %s;
            """,
            (ledger_entry_id,),
        ).fetchone()


def insert_expense(vendor: str, expense_date: str, amount, category: str | None, notes: str | None, created_by_user_id: int | None) -> int:
    with get_db_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO expenses (vendor, expense_date, amount, category, notes, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (vendor, expense_date, amount, category, notes, created_by_user_id),
        ).fetchone()
        return row["id"]


def insert_expense_file(
    expense_id: int,
    bucket: str,
    object_path: str,
    original_filename: str,
    content_type: str,
    file_size_bytes: int,
    sha256: str,
    uploaded_by_user_id: int | None,
):
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO expense_files
              (expense_id, bucket, object_path, original_filename, content_type, file_size_bytes, sha256, uploaded_by_user_id)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                expense_id,
                bucket,
                object_path,
                original_filename,
                content_type,
                file_size_bytes,
                sha256,
                uploaded_by_user_id,
            ),
        )


def get_expenses_with_files():
    """
    Returns a list of expenses; each expense has a `files` list attached.
    """
    with get_db_connection() as conn:
        expenses = conn.execute(
            """
            SELECT *
            FROM expenses
            ORDER BY expense_date DESC, id DESC;
            """
        ).fetchall()

        files = conn.execute(
            """
            SELECT *
            FROM expense_files
            ORDER BY created_at DESC, id DESC;
            """
        ).fetchall()

    # attach files to expenses
    by_id = {e["id"]: dict(e) for e in expenses}
    for e in by_id.values():
        e["files"] = []

    for f in files:
        eid = f["expense_id"]
        if eid in by_id:
            by_id[eid]["files"].append(dict(f))

    return list(by_id.values())

def get_expense_file_by_id(file_id: int):
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT * FROM expense_files WHERE id = %s;",
            (file_id,),
        ).fetchone()
