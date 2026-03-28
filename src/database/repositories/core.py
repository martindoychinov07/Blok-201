import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _id(self) -> str:
        return str(uuid4())

    def bootstrap_defaults(self, patient_id: str, device_id: str) -> None:
        now = utc_now()

        owner_id = "user-owner"
        caregiver_id = "user-caregiver"
        self.conn.execute(
            """
            INSERT OR IGNORE INTO users (id, email, password_hash, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (owner_id, "owner@example.local", "demo", "Primary Caregiver", "admin", now),
        )
        self.conn.execute(
            """
            INSERT OR IGNORE INTO users (id, email, password_hash, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (caregiver_id, "caregiver@example.local", "demo", "Secondary Caregiver", "caregiver", now),
        )

        self.conn.execute(
            """
            INSERT OR IGNORE INTO patients (id, primary_user_id, full_name, dob, diagnosis_notes, preferences_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                owner_id,
                "Demo Patient",
                "1948-01-01",
                "Mild to moderate dementia",
                json.dumps(["likes tea in the morning", "prefers quiet rooms"]),
                now,
            ),
        )

        self.conn.execute(
            """
            INSERT OR IGNORE INTO caregivers (id, patient_id, user_id, relation_type, notify_warning, notify_critical, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("cg-1", patient_id, caregiver_id, "family", 1, 1, now),
        )

        self.conn.execute(
            """
            INSERT OR IGNORE INTO devices (id, patient_id, serial_no, model, firmware_version, last_seen_at, battery_pct, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (device_id, patient_id, "RPI-DEMO-001", "Raspberry Pi", "0.1.0", now, 100.0, "online"),
        )

        self.conn.execute(
            """
            INSERT OR IGNORE INTO zones (id, patient_id, name, center_lat, center_lon, radius_m, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("zone-home", patient_id, "Home", 42.6977, 23.3219, 180.0, 1, now),
        )
        self.conn.commit()

    def get_patient_profile(self, patient_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM patients WHERE id = ?",
            (patient_id,),
        ).fetchone()
        return dict(row) if row else None

    def ensure_device(self, patient_id: str, device_id: str) -> None:
        now = utc_now()
        row = self.conn.execute(
            "SELECT id, patient_id FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()

        if row is None:
            self.conn.execute(
                """
                INSERT INTO devices (id, patient_id, serial_no, model, firmware_version, last_seen_at, battery_pct, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    patient_id,
                    f"AUTO-{device_id}",
                    "Ingest Client",
                    "0.1.0",
                    now,
                    None,
                    "online",
                ),
            )
        else:
            if row["patient_id"] != patient_id:
                self.conn.execute(
                    "UPDATE devices SET patient_id = ?, last_seen_at = ?, status = ? WHERE id = ?",
                    (patient_id, now, "online", device_id),
                )
            else:
                self.conn.execute(
                    "UPDATE devices SET last_seen_at = ?, status = ? WHERE id = ?",
                    (now, "online", device_id),
                )
        self.conn.commit()

    def list_people_profiles(self, patient_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM people_profiles
            WHERE patient_id = ? AND is_active = 1
            ORDER BY updated_at DESC
            """,
            (patient_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def upsert_person_profile(
        self,
        patient_id: str,
        name: str,
        person_type: str,
        relationship_to_patient: str,
        confidence: float,
        notes: str = "",
    ) -> str:
        now = utc_now()
        existing = self.conn.execute(
            """
            SELECT id, confidence FROM people_profiles
            WHERE patient_id = ? AND lower(name) = lower(?)
            """,
            (patient_id, name),
        ).fetchone()
        if existing:
            person_id = existing["id"]
            new_conf = max(existing["confidence"], confidence)
            self.conn.execute(
                """
                UPDATE people_profiles
                SET person_type = ?, relationship_to_patient = ?, confidence = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (person_type, relationship_to_patient, new_conf, notes, now, person_id),
            )
        else:
            person_id = self._id()
            self.conn.execute(
                """
                INSERT INTO people_profiles
                  (id, patient_id, name, person_type, relationship_to_patient, phone, notes, confidence, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    patient_id,
                    name,
                    person_type,
                    relationship_to_patient,
                    "",
                    notes,
                    confidence,
                    1,
                    now,
                    now,
                ),
            )
        self.conn.commit()
        return person_id

    def create_conversation(self, patient_id: str, device_id: str, language: str = "bg") -> str:
        self.ensure_device(patient_id=patient_id, device_id=device_id)
        now = utc_now()
        conversation_id = self._id()
        self.conn.execute(
            """
            INSERT INTO conversations (id, patient_id, device_id, started_at, ended_at, language, summary_text, summary_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (conversation_id, patient_id, device_id, now, None, language, None, None, now),
        )
        self.conn.commit()
        return conversation_id

    def add_transcript_segment(
        self,
        conversation_id: str,
        patient_id: str,
        ts_start_ms: int,
        ts_end_ms: int,
        text: str,
        stt_engine: str,
        stt_confidence: float,
        speaker_label: str = "unknown",
    ) -> str:
        transcript_id = self._id()
        now = utc_now()
        self.conn.execute(
            """
            INSERT INTO transcripts
                (id, conversation_id, patient_id, ts_start_ms, ts_end_ms, speaker_label, text, stt_engine, stt_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transcript_id,
                conversation_id,
                patient_id,
                ts_start_ms,
                ts_end_ms,
                speaker_label,
                text,
                stt_engine,
                stt_confidence,
                now,
            ),
        )
        self.conn.commit()
        return transcript_id

    def finalize_conversation(self, conversation_id: str, summary_text: str, summary_confidence: float) -> None:
        now = utc_now()
        self.conn.execute(
            """
            UPDATE conversations
            SET ended_at = ?, summary_text = ?, summary_confidence = ?
            WHERE id = ?
            """,
            (now, summary_text, summary_confidence, conversation_id),
        )
        self.conn.commit()

    def add_fact(
        self,
        patient_id: str,
        conversation_id: str | None,
        transcript_id: str | None,
        fact_type: str,
        subject_ref: str,
        predicate: str,
        object_value: str,
        confidence: float,
        source_evidence: str,
        status: str = "active",
    ) -> str:
        now = utc_now()
        fact_id = self._id()
        self.conn.execute(
            """
            INSERT INTO extracted_facts
                (id, patient_id, conversation_id, transcript_id, fact_type, subject_ref, predicate, object_value,
                 temporal_context, confidence, status, source_evidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact_id,
                patient_id,
                conversation_id,
                transcript_id,
                fact_type,
                subject_ref,
                predicate,
                object_value,
                "",
                confidence,
                status,
                source_evidence,
                now,
                now,
            ),
        )
        self.conn.commit()
        return fact_id

    def add_or_merge_fact(
        self,
        patient_id: str,
        conversation_id: str | None,
        fact_type: str,
        subject_ref: str,
        predicate: str,
        object_value: str,
        confidence: float,
        source_evidence: str,
    ) -> str:
        now = utc_now()
        existing = self.conn.execute(
            """
            SELECT id, confidence FROM extracted_facts
            WHERE patient_id = ? AND fact_type = ? AND subject_ref = ? AND predicate = ?
              AND lower(object_value) = lower(?) AND status = 'active'
            """,
            (patient_id, fact_type, subject_ref, predicate, object_value),
        ).fetchone()
        if existing:
            fact_id = existing["id"]
            merged_conf = max(float(existing["confidence"]), confidence)
            self.conn.execute(
                """
                UPDATE extracted_facts
                SET confidence = ?, source_evidence = ?, updated_at = ?
                WHERE id = ?
                """,
                (merged_conf, source_evidence, now, fact_id),
            )
            self.conn.commit()
            return fact_id
        return self.add_fact(
            patient_id=patient_id,
            conversation_id=conversation_id,
            transcript_id=None,
            fact_type=fact_type,
            subject_ref=subject_ref,
            predicate=predicate,
            object_value=object_value,
            confidence=confidence,
            source_evidence=source_evidence,
        )

    def add_reminder(
        self,
        patient_id: str,
        source_conversation_id: str | None,
        title: str,
        details: str,
        due_at: str | None,
        recurrence_rule: str | None,
        priority: str,
        confidence: float,
    ) -> str:
        now = utc_now()
        reminder_id = self._id()
        self.conn.execute(
            """
            INSERT INTO reminders
                (id, patient_id, source_conversation_id, title, details, due_at, recurrence_rule, priority, status, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reminder_id,
                patient_id,
                source_conversation_id,
                title,
                details,
                due_at,
                recurrence_rule,
                priority,
                "active",
                confidence,
                now,
                now,
            ),
        )
        self.conn.commit()
        return reminder_id

    def add_or_merge_reminder(
        self,
        patient_id: str,
        source_conversation_id: str | None,
        title: str,
        details: str,
        due_at: str | None,
        recurrence_rule: str | None,
        priority: str,
        confidence: float,
    ) -> str:
        now = utc_now()
        normalized_due = due_at or ""
        normalized_recur = recurrence_rule or ""
        normalized_details = details.strip().lower()

        existing = self.conn.execute(
            """
            SELECT id, confidence
            FROM reminders
            WHERE patient_id = ?
              AND lower(title) = lower(?)
              AND lower(trim(details)) = ?
              AND coalesce(due_at, '') = ?
              AND coalesce(recurrence_rule, '') = ?
              AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (patient_id, title, normalized_details, normalized_due, normalized_recur),
        ).fetchone()
        if existing:
            reminder_id = existing["id"]
            merged_conf = max(float(existing["confidence"] or 0.0), confidence)
            self.conn.execute(
                """
                UPDATE reminders
                SET details = ?, due_at = COALESCE(?, due_at), recurrence_rule = COALESCE(?, recurrence_rule),
                    priority = ?, confidence = ?, updated_at = ?
                WHERE id = ?
                """,
                (details, due_at, recurrence_rule, priority, merged_conf, now, reminder_id),
            )
            self.conn.commit()
            return reminder_id

        return self.add_reminder(
            patient_id=patient_id,
            source_conversation_id=source_conversation_id,
            title=title,
            details=details,
            due_at=due_at,
            recurrence_rule=recurrence_rule,
            priority=priority,
            confidence=confidence,
        )

    def list_reminders(self, patient_id: str, status: str = "active", limit: int = 100) -> list[dict[str, Any]]:
        if status == "all":
            rows = self.conn.execute(
                """
                SELECT * FROM reminders
                WHERE patient_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (patient_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM reminders
                WHERE patient_id = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (patient_id, status, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_events(self, patient_id: str, limit: int = 100) -> list[dict[str, Any]]:
        reminder_rows = self.conn.execute(
            """
            SELECT id, title, details, due_at, recurrence_rule, priority, confidence, status, created_at
            FROM reminders
            WHERE patient_id = ?
              AND status = 'active'
              AND (
                    lower(title) LIKE 'meet %'
                 OR lower(title) LIKE '%party%'
                 OR lower(title) LIKE '%birthday%'
                 OR lower(details) LIKE '%birthday%'
                 OR lower(details) LIKE '%party%'
                 OR lower(details) LIKE '%invited%'
                 OR lower(details) LIKE '%рожден%'
                 OR lower(details) LIKE '%парти%'
                 OR lower(details) LIKE '%покан%'
                 OR lower(details) LIKE '%срещ%'
              )
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        ).fetchall()

        fact_rows = self.conn.execute(
            """
            SELECT id, predicate, object_value, confidence, created_at, updated_at
            FROM extracted_facts
            WHERE patient_id = ?
              AND fact_type = 'event'
              AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        ).fetchall()

        events: list[dict[str, Any]] = []
        for row in reminder_rows:
            r = dict(row)
            events.append(
                {
                    "id": r["id"],
                    "source": "reminder",
                    "title": r["title"],
                    "details": r["details"],
                    "due_at": r["due_at"],
                    "recurrence_rule": r["recurrence_rule"],
                    "priority": r["priority"],
                    "status": r["status"],
                    "confidence": r["confidence"],
                    "created_at": r["created_at"],
                }
            )

        for row in fact_rows:
            f = dict(row)
            events.append(
                {
                    "id": f["id"],
                    "source": "memory_fact",
                    "title": f["predicate"],
                    "details": f["object_value"],
                    "due_at": None,
                    "recurrence_rule": None,
                    "priority": "medium",
                    "status": "active",
                    "confidence": f["confidence"],
                    "created_at": f["updated_at"] or f["created_at"],
                }
            )

        events.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return events[:limit]

    def set_reminder_status(self, patient_id: str, reminder_id: str, status: str) -> bool:
        cur = self.conn.execute(
            """
            UPDATE reminders
            SET status = ?, updated_at = ?
            WHERE id = ? AND patient_id = ?
            """,
            (status, utc_now(), reminder_id, patient_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_memory_context(self, patient_id: str) -> dict[str, Any]:
        profile = self.get_patient_profile(patient_id)

        reminders = self.conn.execute(
            """
            SELECT id, title, details, due_at, priority, status
            FROM reminders
            WHERE patient_id = ? AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (patient_id,),
        ).fetchall()

        risks = self.conn.execute(
            """
            SELECT object_value, confidence, source_evidence
            FROM extracted_facts
            WHERE patient_id = ? AND fact_type = 'risk_note' AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            (patient_id,),
        ).fetchall()

        recent_summary = self.conn.execute(
            """
            SELECT summary_text, ended_at
            FROM conversations
            WHERE patient_id = ? AND summary_text IS NOT NULL
            ORDER BY ended_at DESC
            LIMIT 1
            """,
            (patient_id,),
        ).fetchone()

        people = self.conn.execute(
            """
            SELECT name, person_type, relationship_to_patient, confidence
            FROM people_profiles
            WHERE patient_id = ? AND is_active = 1
            ORDER BY confidence DESC, updated_at DESC
            LIMIT 10
            """,
            (patient_id,),
        ).fetchall()

        return {
            "profile": dict(profile) if profile else None,
            "active_reminders": [dict(r) for r in reminders],
            "active_risks": [dict(r) for r in risks],
            "recent_summary": dict(recent_summary) if recent_summary else None,
            "important_people": [dict(p) for p in people],
        }

    def get_active_zone(self, patient_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT * FROM zones
            WHERE patient_id = ? AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (patient_id,),
        ).fetchone()
        return dict(row) if row else None

    def add_gps_event(
        self,
        patient_id: str,
        device_id: str,
        lat: float,
        lon: float,
        speed_mps: float,
        accuracy_m: float,
        inside_zone: bool | None,
        zone_id: str | None,
    ) -> str:
        self.ensure_device(patient_id=patient_id, device_id=device_id)
        event_id = self._id()
        self.conn.execute(
            """
            INSERT INTO gps_events
                (id, patient_id, device_id, ts, lat, lon, speed_mps, accuracy_m, inside_zone, zone_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                patient_id,
                device_id,
                utc_now(),
                lat,
                lon,
                speed_mps,
                accuracy_m,
                int(inside_zone) if inside_zone is not None else None,
                zone_id,
            ),
        )
        self.conn.commit()
        return event_id

    def add_fall_event(
        self,
        patient_id: str,
        device_id: str,
        impact_g: float,
        orientation_delta: float,
        inactivity_sec: int,
        confidence: float,
        is_confirmed: bool,
    ) -> str:
        self.ensure_device(patient_id=patient_id, device_id=device_id)
        event_id = self._id()
        self.conn.execute(
            """
            INSERT INTO fall_events
                (id, patient_id, device_id, ts, impact_g, orientation_delta, inactivity_sec, confidence, is_confirmed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                patient_id,
                device_id,
                utc_now(),
                impact_g,
                orientation_delta,
                inactivity_sec,
                confidence,
                int(is_confirmed),
            ),
        )
        self.conn.commit()
        return event_id

    def create_alert(
        self,
        patient_id: str,
        device_id: str,
        alert_type: str,
        severity: str,
        title: str,
        payload: dict[str, Any],
    ) -> str:
        self.ensure_device(patient_id=patient_id, device_id=device_id)
        alert_id = self._id()
        self.conn.execute(
            """
            INSERT INTO alerts
                (id, patient_id, device_id, alert_type, severity, title, payload_json, status, triggered_at, acknowledged_by, acknowledged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert_id,
                patient_id,
                device_id,
                alert_type,
                severity,
                title,
                json.dumps(payload, ensure_ascii=True),
                "open",
                utc_now(),
                None,
                None,
            ),
        )
        self.conn.commit()
        return alert_id

    def list_alerts(self, patient_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM alerts
            WHERE patient_id = ?
            ORDER BY triggered_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                payload = json.loads(item.get("payload_json", "{}"))
            except Exception:
                payload = {}
            item["payload"] = payload
            item["message"] = payload.get("message", "")
            output.append(item)
        return output

    def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        cur = self.conn.execute(
            """
            UPDATE alerts
            SET status = 'ack', acknowledged_by = ?, acknowledged_at = ?
            WHERE id = ?
            """,
            (user_id, utc_now(), alert_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_memory(self, patient_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM extracted_facts
            WHERE patient_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
