import sqlite3
from datetime import datetime, timezone

from app.schemas import AnalysisResult, TranscriptIn


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class MemoryService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save_raw_transcript(self, payload: TranscriptIn) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO transcripts (patient_id, timestamp, text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (payload.patient_id, payload.timestamp.isoformat(), payload.text, utc_now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def persist_analysis(self, patient_id: str, transcript_id: int, analysis: AnalysisResult) -> dict[str, int]:
        counts = {
            "people": 0,
            "appointments": 0,
            "reminders": 0,
            "facts": 0,
        }

        now = utc_now_iso()
        try:
            with self.conn:
                for person in analysis.people:
                    existing = self.conn.execute(
                        """
                        SELECT id FROM people
                        WHERE patient_id = ? AND lower(name) = lower(?)
                          AND coalesce(lower(relationship), '') = coalesce(lower(?), '')
                        LIMIT 1
                        """,
                        (patient_id, person.name, person.relationship),
                    ).fetchone()
                    if existing:
                        self.conn.execute(
                            "UPDATE people SET transcript_id = ?, updated_at = ? WHERE id = ?",
                            (transcript_id, now, existing["id"]),
                        )
                    else:
                        self.conn.execute(
                            """
                            INSERT INTO people (patient_id, transcript_id, name, relationship, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (patient_id, transcript_id, person.name, person.relationship, now, now),
                        )
                    counts["people"] += 1

                for appointment in analysis.appointments:
                    self.conn.execute(
                        """
                        INSERT INTO appointments (patient_id, transcript_id, title, doctor, time_text, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            patient_id,
                            transcript_id,
                            appointment.title,
                            appointment.doctor,
                            appointment.time_text,
                            now,
                        ),
                    )
                    counts["appointments"] += 1

                for reminder in analysis.reminders:
                    self.conn.execute(
                        """
                        INSERT INTO reminders (patient_id, transcript_id, type, text, time_text, status, created_at)
                        VALUES (?, ?, ?, ?, ?, 'active', ?)
                        """,
                        (
                            patient_id,
                            transcript_id,
                            reminder.type,
                            reminder.text,
                            reminder.time_text,
                            now,
                        ),
                    )
                    counts["reminders"] += 1

                for med in analysis.medications:
                    self.conn.execute(
                        """
                        INSERT INTO facts (patient_id, transcript_id, fact_type, content, created_at)
                        VALUES (?, ?, 'medication', ?, ?)
                        """,
                        (patient_id, transcript_id, med, now),
                    )
                    counts["facts"] += 1

                for note in analysis.safety_notes:
                    self.conn.execute(
                        """
                        INSERT INTO facts (patient_id, transcript_id, fact_type, content, created_at)
                        VALUES (?, ?, 'safety_note', ?, ?)
                        """,
                        (patient_id, transcript_id, note, now),
                    )
                    counts["facts"] += 1

                for fact in analysis.important_facts:
                    self.conn.execute(
                        """
                        INSERT INTO facts (patient_id, transcript_id, fact_type, content, created_at)
                        VALUES (?, ?, 'important_fact', ?, ?)
                        """,
                        (patient_id, transcript_id, fact, now),
                    )
                    counts["facts"] += 1
        except sqlite3.Error:
            raise

        return counts

    def list_reminders(self, patient_id: str, status: str = "active", limit: int = 50) -> list[dict]:
        if status == "all":
            rows = self.conn.execute(
                """
                SELECT id, patient_id, transcript_id, type, text, time_text, status, created_at
                FROM reminders
                WHERE patient_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (patient_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT id, patient_id, transcript_id, type, text, time_text, status, created_at
                FROM reminders
                WHERE patient_id = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (patient_id, status, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_reminder_status(self, patient_id: str, reminder_id: int, status: str) -> bool:
        cur = self.conn.execute(
            """
            UPDATE reminders
            SET status = ?
            WHERE id = ? AND patient_id = ?
            """,
            (status, reminder_id, patient_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_appointments(self, patient_id: str, limit: int = 30) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, patient_id, transcript_id, title, doctor, time_text, created_at
            FROM appointments
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_facts(self, patient_id: str, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, patient_id, transcript_id, fact_type, content, created_at
            FROM facts
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_recent_transcripts(self, patient_id: str, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, patient_id, timestamp, text, created_at
            FROM transcripts
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
