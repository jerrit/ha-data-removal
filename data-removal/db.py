"""
db.py — Database layer for the data removal system.

SQLite database is stored at /data/findings.db so it persists across
Home Assistant addon restarts.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/data/findings.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    with conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT    NOT NULL,
                first_name   TEXT    NOT NULL DEFAULT '',
                last_name    TEXT    NOT NULL DEFAULT '',
                city         TEXT    DEFAULT '',
                state        TEXT    DEFAULT '',
                state_full   TEXT    DEFAULT '',
                email        TEXT    DEFAULT '',
                phone        TEXT    DEFAULT '',
                notes        TEXT    DEFAULT '',
                is_default   INTEGER DEFAULT 0,
                created_at   TEXT    NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sites (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                name                 TEXT    NOT NULL UNIQUE,
                url                  TEXT    NOT NULL,
                search_url_template  TEXT,
                opt_out_url          TEXT,
                opt_out_method       TEXT,
                opt_out_instructions TEXT,
                estimated_days       INTEGER DEFAULT 30,
                enabled              INTEGER DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id          INTEGER NOT NULL,
                user_id          INTEGER,
                scan_date        TEXT    NOT NULL,
                profile_found    INTEGER NOT NULL DEFAULT 0,
                profile_url      TEXT,
                data_fields_json TEXT,
                status           TEXT    NOT NULL DEFAULT 'scanning',
                FOREIGN KEY (site_id) REFERENCES sites(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id          INTEGER NOT NULL,
                request_date     TEXT    NOT NULL,
                method           TEXT    NOT NULL,
                confirmation     INTEGER DEFAULT 0,
                next_rescan_date TEXT,
                notes            TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(id)
            )
        """)

    _run_migrations(conn)
    conn.close()


def _run_migrations(conn):
    migrations = [
        "ALTER TABLE scans ADD COLUMN user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE sites ADD COLUMN search_url_template TEXT",
        "ALTER TABLE sites ADD COLUMN enabled INTEGER DEFAULT 1",
        "ALTER TABLE requests ADD COLUMN email_text TEXT",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass


# ── USERS ──────────────────────────────────────────────────────────────────── #

def seed_default_user() -> dict | None:
    """No-op — users are added via the web UI."""
    return get_default_user()


def create_user(
    display_name: str,
    first_name: str,
    last_name: str,
    city: str = "",
    state: str = "",
    state_full: str = "",
    email: str = "",
    phone: str = "",
    notes: str = "",
    is_default: int = 0,
) -> dict:
    conn = get_db()
    with conn:
        cursor = conn.execute("""
            INSERT INTO users
                (display_name, first_name, last_name, city, state, state_full,
                 email, phone, notes, is_default, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            display_name, first_name, last_name, city, state, state_full,
            email, phone, notes, is_default,
            datetime.utcnow().isoformat(),
        ))
        user_id = cursor.lastrowid
    conn.close()
    return get_user(user_id)


def get_all_users() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM users ORDER BY is_default DESC, display_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_default_user() -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users ORDER BY is_default DESC, id LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(user_id: int, **fields) -> None:
    allowed = {
        "display_name", "first_name", "last_name", "city", "state",
        "state_full", "email", "phone", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    placeholders = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]
    conn = get_db()
    with conn:
        conn.execute(f"UPDATE users SET {placeholders} WHERE id = ?", values)
    conn.close()


def delete_user(user_id: int) -> None:
    conn = get_db()
    with conn:
        scan_ids = [
            r[0] for r in conn.execute(
                "SELECT id FROM scans WHERE user_id = ?", (user_id,)
            ).fetchall()
        ]
        for sid in scan_ids:
            conn.execute("DELETE FROM requests WHERE scan_id = ?", (sid,))
        conn.execute("DELETE FROM scans WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.close()


def get_user_scan_counts() -> dict[int, dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT user_id,
               SUM(CASE WHEN status = 'found'            THEN 1 ELSE 0 END) AS found,
               SUM(CASE WHEN status = 'pending_removal'  THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN status = 'removed'          THEN 1 ELSE 0 END) AS removed
        FROM scans
        WHERE user_id IS NOT NULL
        GROUP BY user_id
    """).fetchall()
    conn.close()
    return {r["user_id"]: dict(r) for r in rows}


# ── SITES ──────────────────────────────────────────────────────────────────── #

def seed_sites(sites_data: list[dict]):
    conn = get_db()
    with conn:
        for site in sites_data:
            conn.execute("""
                INSERT INTO sites
                    (name, url, search_url_template, opt_out_url, opt_out_method,
                     opt_out_instructions, estimated_days)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    url                  = excluded.url,
                    search_url_template  = excluded.search_url_template,
                    opt_out_url          = excluded.opt_out_url,
                    opt_out_method       = excluded.opt_out_method,
                    opt_out_instructions = excluded.opt_out_instructions,
                    estimated_days       = excluded.estimated_days
            """, (
                site["name"],
                site["url"],
                site.get("search_url_template", ""),
                site.get("opt_out_url", ""),
                site.get("opt_out_method", "form"),
                site.get("opt_out_instructions", ""),
                site.get("estimated_days", 30),
            ))
    conn.close()


def update_site(site_id: int, **fields) -> None:
    allowed = {
        "url", "search_url_template", "opt_out_url", "opt_out_method",
        "opt_out_instructions", "estimated_days",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    placeholders = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [site_id]
    conn = get_db()
    with conn:
        conn.execute(f"UPDATE sites SET {placeholders} WHERE id = ?", values)
    conn.close()


def toggle_site_enabled(site_id: int) -> int:
    conn = get_db()
    row = conn.execute("SELECT enabled FROM sites WHERE id = ?", (site_id,)).fetchone()
    if row is None:
        conn.close()
        return 1
    new_val = 0 if row["enabled"] else 1
    with conn:
        conn.execute("UPDATE sites SET enabled = ? WHERE id = ?", (new_val, site_id))
    conn.close()
    return new_val


def get_all_sites() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM sites ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_site(site_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_site_by_name(name: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM sites WHERE name = ?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── SCANS ──────────────────────────────────────────────────────────────────── #

def insert_scan(
    site_id: int,
    profile_found: bool,
    profile_url: str | None = None,
    data_fields: dict | None = None,
    status: str = "not_found",
    user_id: int | None = None,
) -> int:
    conn = get_db()
    with conn:
        cursor = conn.execute("""
            INSERT INTO scans
                (site_id, user_id, scan_date, profile_found, profile_url, data_fields_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            site_id,
            user_id,
            datetime.utcnow().isoformat(),
            1 if profile_found else 0,
            profile_url,
            json.dumps(data_fields) if data_fields else None,
            status,
        ))
        scan_id = cursor.lastrowid
    conn.close()
    return scan_id


def update_scan_status(scan_id: int, status: str):
    conn = get_db()
    with conn:
        conn.execute("UPDATE scans SET status = ? WHERE id = ?", (status, scan_id))
    conn.close()


def get_scan(scan_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("""
        SELECT s.*, si.name AS site_name, si.opt_out_url, si.opt_out_method,
               si.opt_out_instructions, si.estimated_days,
               u.display_name AS user_display_name
        FROM scans s
        JOIN sites si ON s.site_id = si.id
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (scan_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_scans(user_id: int | None = None) -> list[dict]:
    conn = get_db()
    user_filter = "AND s.user_id = ?" if user_id is not None else ""
    params = (user_id,) if user_id is not None else ()
    rows = conn.execute(f"""
        SELECT
            s.*,
            si.name        AS site_name,
            si.opt_out_url AS site_opt_out_url,
            si.opt_out_method,
            u.display_name AS user_display_name,
            r.request_date,
            r.next_rescan_date,
            r.confirmation
        FROM scans s
        JOIN sites si ON s.site_id = si.id
        LEFT JOIN users u ON s.user_id = u.id
        LEFT JOIN requests r ON r.scan_id = s.id
            AND r.id = (SELECT MAX(id) FROM requests WHERE scan_id = s.id)
        WHERE s.id IN (
            SELECT MAX(id) FROM scans GROUP BY site_id, COALESCE(user_id, -1)
        )
        {user_filter}
        ORDER BY s.scan_date DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scans_for_site(site_id: int, user_id: int | None = None) -> list[dict]:
    conn = get_db()
    extra = "AND s.user_id = ?" if user_id is not None else ""
    params = (site_id, user_id) if user_id is not None else (site_id,)
    rows = conn.execute(f"""
        SELECT s.*, r.request_date, r.method AS request_method,
               r.next_rescan_date, r.notes, r.confirmation,
               u.display_name AS user_display_name
        FROM scans s
        LEFT JOIN requests r ON r.scan_id = s.id
            AND r.id = (SELECT MAX(id) FROM requests WHERE scan_id = s.id)
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.site_id = ? {extra}
        ORDER BY s.scan_date DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scans_due_for_rescan() -> list[dict]:
    now = datetime.utcnow().isoformat()
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, r.next_rescan_date, si.name AS site_name,
               s.user_id AS rescan_user_id
        FROM scans s
        JOIN requests r ON r.scan_id = s.id
        JOIN sites si ON s.site_id = si.id
        WHERE r.next_rescan_date <= ?
          AND s.status = 'pending_removal'
    """, (now,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── REQUESTS ───────────────────────────────────────────────────────────────── #

def insert_request(
    scan_id: int,
    method: str,
    confirmation: bool = False,
    notes: str | None = None,
    email_text: str | None = None,
) -> int:
    next_rescan = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn = get_db()
    with conn:
        cursor = conn.execute("""
            INSERT INTO requests
                (scan_id, request_date, method, confirmation, next_rescan_date,
                 notes, email_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            scan_id,
            datetime.utcnow().isoformat(),
            method,
            1 if confirmation else 0,
            next_rescan,
            notes,
            email_text,
        ))
        request_id = cursor.lastrowid
        conn.execute(
            "UPDATE scans SET status = 'pending_removal' WHERE id = ?", (scan_id,)
        )
    conn.close()
    return request_id


def get_requests_for_scan(scan_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM requests WHERE scan_id = ? ORDER BY request_date DESC",
        (scan_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── DASHBOARD STATS ────────────────────────────────────────────────────────── #

def get_dashboard_stats(user_id: int | None = None) -> dict:
    conn = get_db()
    uid_filter = "AND s.user_id = ?" if user_id is not None else ""
    p = (user_id,) if user_id is not None else ()

    total_sites = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]

    data_found_on = conn.execute(f"""
        SELECT COUNT(DISTINCT s.site_id) FROM scans s
        WHERE s.profile_found = 1
          AND s.status NOT IN ('removed', 'not_found', 'error')
          {uid_filter}
    """, p).fetchone()[0]

    total_requests = conn.execute(f"""
        SELECT COUNT(*) FROM requests r
        JOIN scans s ON r.scan_id = s.id
        WHERE 1=1 {uid_filter}
    """, p).fetchone()[0]

    confirmed_removed = conn.execute(f"""
        SELECT COUNT(*) FROM scans s
        WHERE s.status = 'removed' {uid_filter}
    """, p).fetchone()[0]

    conn.close()
    return {
        "total_sites":       total_sites,
        "data_found_on":     data_found_on,
        "total_requests":    total_requests,
        "confirmed_removed": confirmed_removed,
    }


def prune_old_scans(keep_per_site: int = 10) -> int:
    prunable = "('not_found', 'removed', 'error', 'blocked')"
    conn = get_db()

    rows = conn.execute(f"""
        SELECT id FROM (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY site_id, COALESCE(user_id, -1)
                       ORDER BY scan_date DESC
                   ) AS rn
            FROM scans
            WHERE status IN {prunable}
        )
        WHERE rn > ?
    """, (keep_per_site,)).fetchall()

    if not rows:
        conn.close()
        return 0

    delete_ids = [r[0] for r in rows]
    placeholders = ",".join("?" * len(delete_ids))

    with conn:
        conn.execute(
            f"DELETE FROM requests WHERE scan_id IN ({placeholders})", delete_ids
        )
        cursor = conn.execute(
            f"DELETE FROM scans WHERE id IN ({placeholders})", delete_ids
        )
        deleted = cursor.rowcount

    conn.close()
    return deleted
