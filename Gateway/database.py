# Saves sensor readings and events so they can be reviewed later.
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile

SIMULATION_MODE = os.getenv("SMARTSEAL_SIMULATION", "0") == "1"
DATA_DIRECTORY = Path(__file__).resolve().parent
if SIMULATION_MODE:
    DATA_DIRECTORY = DATA_DIRECTORY / "simulation"

DB_NAME = DATA_DIRECTORY / "smartseal.db"
IMAGE_FOLDER = DB_NAME.parent / "images"
ARCHIVE_DIRECTORY = DB_NAME.parent / "archives"
RETENTION_DAYS = 90


def _utc_cutoff():
    return datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _delete_unreferenced_images():
    referenced = set()
    conn = sqlite3.connect(DB_NAME)
    try:
        referenced.update(
            row[0] for row in conn.execute(
                "SELECT image_path FROM events "
                "WHERE image_path IS NOT NULL AND image_path != ''"
            )
        )
        referenced.update(
            row[0] for row in conn.execute(
                "SELECT image_filename FROM artifact_jobs "
                "WHERE image_filename IS NOT NULL AND image_filename != ''"
            )
        )
    finally:
        conn.close()

    for archive_path in ARCHIVE_DIRECTORY.glob("*.csv"):
        try:
            with archive_path.open(newline="", encoding="utf-8") as archive_file:
                referenced.update(
                    (row.get("image_path") or "").strip()
                    for row in csv.DictReader(archive_file)
                    if (row.get("image_path") or "").strip()
                )
        except (OSError, csv.Error):
            # If an archive cannot be inspected, preserve all images rather
            # than risk removing evidence that it may still reference.
            return

    image_folder = IMAGE_FOLDER.resolve()
    for image_path in IMAGE_FOLDER.glob("*"):
        if image_path.name not in referenced and image_path.is_file():
            resolved = image_path.resolve()
            if resolved.parent == image_folder:
                resolved.unlink()


def apply_retention_policy():
    cutoff = _utc_cutoff()
    conn = sqlite3.connect(DB_NAME)
    try:
        # Compare parsed timestamps instead of relying on SQLite's lexical
        # ordering. Legacy/manual rows may use another ISO-8601 timezone
        # format, and missing or malformed timestamps must not bypass the
        # fixed retention period indefinitely.
        last_id = None
        while True:
            if last_id is None:
                rows = conn.execute(
                    "SELECT id, timestamp FROM events ORDER BY id LIMIT 1000"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, timestamp FROM events WHERE id > ? ORDER BY id LIMIT 1000",
                    (last_id,),
                ).fetchall()
            if not rows:
                break

            expired_ids = []
            for event_id, timestamp in rows:
                last_id = event_id
                event_time = _parse_timestamp(timestamp)
                if event_time is None or event_time < cutoff:
                    expired_ids.append((event_id,))
            if expired_ids:
                conn.executemany("DELETE FROM events WHERE id = ?", expired_ids)
        conn.commit()
    finally:
        conn.close()

    ARCHIVE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for archive_path in ARCHIVE_DIRECTORY.glob("*.csv"):
        try:
            with archive_path.open(newline="", encoding="utf-8") as archive_file:
                reader = csv.DictReader(archive_file)
                fieldnames = reader.fieldnames
                rows = list(reader)
        except (OSError, csv.Error):
            continue

        # Every record must expire. A missing or malformed timestamp cannot
        # prove that a row is still within the retention period, so purge it.
        retained_rows = [
            row for row in rows
            if (
                (event_time := _parse_timestamp(row.get("timestamp"))) is not None
                and event_time >= cutoff
            )
        ]
        if len(retained_rows) == len(rows):
            continue

        if not retained_rows:
            archive_path.unlink()
            continue

        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                newline="",
                encoding="utf-8",
                dir=archive_path.parent,
                prefix=f".{archive_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                writer = csv.DictWriter(
                    temporary_file,
                    fieldnames=fieldnames,
                    extrasaction="ignore",
                )
                writer.writeheader()
                writer.writerows(retained_rows)
            os.replace(temporary_path, archive_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    _delete_unreferenced_images()


def init_database():
    # Create the local SQLite database and its event table if they do not exist.
    DB_NAME.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix" and SIMULATION_MODE:
        DB_NAME.parent.chmod(0o700)
    if os.name == "posix" and DB_NAME.exists() and not DB_NAME.is_symlink():
        DB_NAME.chmod(0o600)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        seal_id INTEGER,
        event_sequence INTEGER,
        temperature REAL,
        tamper INTEGER,
        vibration REAL,
        movement_type INTEGER DEFAULT 0,
        image_path TEXT,
        ai_analysis TEXT,
        gps_latitude REAL,
        gps_longitude REAL
    )
    """)

    # Add newer columns when opening a database created by an older version.
    for column in (
        "event_sequence", "movement_type", "image_path", "ai_analysis",
        "gps_latitude", "gps_longitude",
    ):
        try:
            if column in ("event_sequence", "movement_type"):
                column_type = "INTEGER"
            elif column in ("gps_latitude", "gps_longitude"):
                column_type = "REAL"
            else:
                column_type = "TEXT"
            cur.execute(f"ALTER TABLE events ADD COLUMN {column} {column_type}")
        except sqlite3.OperationalError:
            pass

    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_events_seal_sequence
    ON events(seal_id, event_sequence)
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS seal_status(
        seal_id INTEGER PRIMARY KEY,
        last_seen DATETIME NOT NULL,
        last_event_sequence INTEGER,
        last_delivery_failure DATETIME
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dashboard_users(
        username TEXT PRIMARY KEY COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS artifact_jobs(
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        seal_id INTEGER NOT NULL,
        event_sequence INTEGER NOT NULL,
        packet_json TEXT NOT NULL,
        image_filename TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(seal_id, event_sequence)
    )
    """)

    conn.commit()
    conn.close()
    if os.name == "posix":
        DB_NAME.chmod(0o600)
        for directory in (IMAGE_FOLDER, ARCHIVE_DIRECTORY):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory.chmod(0o700)
            for stored_file in directory.iterdir():
                if stored_file.is_file() and not stored_file.is_symlink():
                    stored_file.chmod(0o600)
    apply_retention_policy()


def clear_event_history():
    conn = sqlite3.connect(DB_NAME)
    with conn:
        conn.execute(
            """
            DELETE FROM events
            WHERE COALESCE(image_path, '') = ''
              AND COALESCE(ai_analysis, '') = ''
            """
        )
    conn.close()
    _delete_unreferenced_images()


def clear_event_history_all():
    """Clear current events; keep production replay state intact."""
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute("DELETE FROM events")
            # Simulation has an isolated database, so its synthetic counter
            # can safely restart. Real seal replay marks stay in the real DB.
            if SIMULATION_MODE:
                conn.execute("DELETE FROM seal_status")
    finally:
        conn.close()
    # Keep images still referenced by CSV archives; remove only true orphans.
    _delete_unreferenced_images()


def insert_event(packet, image_filename=None, ai_analysis=None):
    # Store one normalized gateway packet and any evidence generated for it.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO events
    (seal_id, event_sequence, temperature, tamper, vibration, movement_type,
     image_path, ai_analysis, gps_latitude, gps_longitude)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        packet["seal_id"],
        packet["event_sequence"],
        packet["temperature"],
        int(packet["tamper"]),
        packet["vibration"],
        packet.get("movement_type", 0),
        image_filename,
        ai_analysis,
        packet.get("gps_latitude"),
        packet.get("gps_longitude"),
    ))

    inserted = cur.rowcount == 1
    conn.commit()
    conn.close()
    return inserted


def accept_event(packet, artifact_required=False):
    """Atomically reject stale sequences and persist a fresh event."""
    conn = sqlite3.connect(DB_NAME)
    try:
        # Acquire the write reservation before reading the high-water mark so
        # two gateway processes cannot both accept out-of-order packets.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT last_event_sequence FROM seal_status WHERE seal_id = ?",
            (packet["seal_id"],),
        ).fetchone()
        last_sequence = row[0] if row and row[0] is not None else None
        if last_sequence is None:
            event_row = conn.execute(
                "SELECT MAX(event_sequence) FROM events WHERE seal_id = ?",
                (packet["seal_id"],),
            ).fetchone()
            last_sequence = event_row[0] if event_row else None

        sequence = packet["event_sequence"]
        if last_sequence is not None and sequence <= last_sequence:
            conn.rollback()
            return False

        cur = conn.execute("""
            INSERT OR IGNORE INTO events
            (seal_id, event_sequence, temperature, tamper, vibration, movement_type,
             image_path, ai_analysis, gps_latitude, gps_longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                packet["seal_id"],
                sequence,
                packet["temperature"],
                int(packet["tamper"]),
                packet["vibration"],
                packet.get("movement_type", 0),
                None,
                "Image analysis queued." if artifact_required else None,
                packet.get("gps_latitude"),
                packet.get("gps_longitude"),
            ))
        if cur.rowcount != 1:
            conn.rollback()
            return False

        conn.execute("""
            INSERT INTO seal_status(seal_id, last_seen, last_event_sequence)
            VALUES (?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(seal_id) DO UPDATE SET
                last_seen = excluded.last_seen,
                last_event_sequence = excluded.last_event_sequence
            """, (packet["seal_id"], sequence))
        if artifact_required:
            conn.execute(
                """
                INSERT INTO artifact_jobs
                    (seal_id, event_sequence, packet_json, status)
                VALUES (?, ?, ?, 'pending')
                """,
                (packet["seal_id"], sequence, json.dumps(packet)),
            )
        conn.commit()
        return True
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def update_event_artifacts(packet, image_filename=None, ai_analysis=None):
    conn = sqlite3.connect(DB_NAME)
    conn.execute(
        """
        UPDATE events
        SET image_path = ?, ai_analysis = ?
        WHERE seal_id = ? AND event_sequence = ?
        """,
        (
            image_filename,
            ai_analysis,
            packet["seal_id"],
            packet["event_sequence"],
        ),
    )
    conn.commit()
    conn.close()


def recover_artifact_jobs():
    """Make interrupted work available to the background worker again."""
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute(
                "UPDATE artifact_jobs SET status = 'pending' WHERE status = 'processing'"
            )
    finally:
        conn.close()


def claim_artifact_job():
    """Atomically claim one durable image-analysis job."""
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT job_id, packet_json, image_filename
            FROM artifact_jobs WHERE status = 'pending'
            ORDER BY job_id LIMIT 1
            """
        ).fetchone()
        if row is None:
            conn.commit()
            return None
        conn.execute(
            "UPDATE artifact_jobs SET status = 'processing' WHERE job_id = ?",
            (row[0],),
        )
        conn.commit()
        return row[0], json.loads(row[1]), row[2]
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def save_artifact_image(job_id, image_filename):
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute(
                "UPDATE artifact_jobs SET image_filename = ? WHERE job_id = ?",
                (image_filename, job_id),
            )
    finally:
        conn.close()


def retry_artifact_job(job_id):
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute(
                "UPDATE artifact_jobs SET status = 'pending' WHERE job_id = ?",
                (job_id,),
            )
    finally:
        conn.close()


def _update_archived_event_artifacts(packet, image_filename, ai_analysis):
    for archive_path in ARCHIVE_DIRECTORY.glob("*.csv"):
        try:
            with archive_path.open(newline="", encoding="utf-8") as archive_file:
                reader = csv.DictReader(archive_file)
                fieldnames = reader.fieldnames
                rows = list(reader)
        except (OSError, csv.Error):
            continue
        if not fieldnames:
            continue

        changed = False
        for row in rows:
            if (
                row.get("seal_id") == str(packet["seal_id"])
                and row.get("event_sequence") == str(packet["event_sequence"])
            ):
                row["image_path"] = image_filename or ""
                safe_analysis = ai_analysis or ""
                if safe_analysis.lstrip().startswith(("=", "+", "-", "@")):
                    safe_analysis = "'" + safe_analysis
                row["ai_analysis"] = safe_analysis
                changed = True
        if not changed:
            continue

        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", newline="", encoding="utf-8", dir=archive_path.parent,
                prefix=f".{archive_path.name}.", suffix=".tmp", delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                writer = csv.DictWriter(
                    temporary_file, fieldnames=fieldnames, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temporary_path, archive_path)
            if os.name == "posix":
                archive_path.chmod(0o600)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


def complete_artifact_job(job_id, packet, image_filename, ai_analysis):
    """Persist results to live/archive history before removing the job."""
    update_event_artifacts(packet, image_filename, ai_analysis)
    _update_archived_event_artifacts(packet, image_filename, ai_analysis)
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            conn.execute("DELETE FROM artifact_jobs WHERE job_id = ?", (job_id,))
    finally:
        conn.close()


def record_seen(packet):
    conn = sqlite3.connect(DB_NAME)
    try:
        with conn:
            row = conn.execute(
                "SELECT last_event_sequence FROM seal_status WHERE seal_id = ?",
                (packet["seal_id"],),
            ).fetchone()
            sequence = packet["event_sequence"]
            if row is not None and row[0] is not None and sequence <= row[0]:
                return False
            conn.execute("""
            INSERT INTO seal_status(seal_id, last_seen, last_event_sequence)
            VALUES (?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(seal_id) DO UPDATE SET
                last_seen = excluded.last_seen,
                last_event_sequence = excluded.last_event_sequence
            """, (packet["seal_id"], sequence))
        return True
    finally:
        conn.close()

def get_stale_seals(timeout_seconds):
    conn = sqlite3.connect(DB_NAME)
    rows = conn.execute("""
    SELECT seal_id, last_seen
    FROM seal_status
    WHERE (julianday('now') - julianday(last_seen)) * 86400 > ?
    """, (timeout_seconds,)).fetchall()
    conn.close()
    return rows


def get_latest_events():
    # Return the complete event history, newest first, for the dashboard.
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    SELECT id, timestamp, seal_id, event_sequence, temperature, tamper,
           vibration, movement_type, image_path, ai_analysis,
           gps_latitude, gps_longitude
    FROM events
    ORDER BY timestamp DESC, id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


def archive_events():
    conn = sqlite3.connect(DB_NAME)
    try:
        rows = conn.execute("""
        SELECT id, timestamp, seal_id, event_sequence, temperature, tamper,
               vibration, movement_type, image_path, ai_analysis,
               gps_latitude, gps_longitude
        FROM events
        ORDER BY timestamp ASC, id ASC
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        return None

    archive_dir = DB_NAME.parent / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / (
        f"SmartSeal_Events_{datetime.now().strftime('%m-%d-%y_%I-%M-%S-%p')}.csv"
    )

    with archive_path.open("w", newline="", encoding="utf-8") as archive_file:
        writer = csv.writer(archive_file)
        writer.writerow((
            "id",
            "timestamp",
            "seal_id",
            "event_sequence",
            "temperature",
            "tamper",
            "vibration",
            "movement_type",
            "image_path",
            "ai_analysis",
            "gps_latitude",
            "gps_longitude",
        ))
        writer.writerows(_spreadsheet_safe_row(row) for row in rows)

    if os.name == "posix":
        archive_path.chmod(0o600)

    return archive_path


def _spreadsheet_safe_row(row):
    """Prefix formula-like text so spreadsheet apps treat it as plain text."""
    safe_row = list(row)
    for index, value in enumerate(safe_row):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            safe_row[index] = "'" + value
    return safe_row
