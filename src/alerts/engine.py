from dataclasses import dataclass
from typing import Any

from src.alerts.notifier import AlertNotifier
from src.database.repositories import Repository


@dataclass
class AlertEngine:
    repo: Repository
    notifier: AlertNotifier
    patient_id: str
    device_id: str

    async def trigger(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        payload: dict[str, Any] | None = None,
        patient_id: str | None = None,
        device_id: str | None = None,
    ) -> str:
        payload = payload or {}
        patient_id = patient_id or self.patient_id
        device_id = device_id or self.device_id
        full_payload = {
            "type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            **payload,
        }

        alert_id = self.repo.create_alert(
            patient_id=patient_id,
            device_id=device_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            payload=full_payload,
        )
        full_payload["alert_id"] = alert_id
        full_payload["patient_id"] = patient_id

        await self.notifier.notify(full_payload)
        return alert_id
