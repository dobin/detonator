import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from ..database import get_db_for_thread, Scan, ScanAlert, Profile
from .mde_client import MDEClient
from ..db_interface import db_scan_add_log, db_scan_change_status_quick

logger = logging.getLogger(__name__)

POLLING_TIME_MINUTES = 10


class AlertMonitorMde:

    def __init__(self, scan_id: int):
        self.scan_id = scan_id
        self.task: Optional[asyncio.Task] = None
        self.db: Optional[Session] = None
        self.client_cache: Dict[str, MDEClient] = {}


    def start_monitoring(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("Alert monitoring task started")


    async def _monitor_loop(self):
        self.db = get_db_for_thread()
        while self.running:
            try:
                # check newest status
                scan = self.db.query(Scan).filter(Scan.id == self.scan_id).first()
                if not scan:
                    break

                stop_time = scan.completed_at + timedelta(minutes=POLLING_TIME_MINUTES)
                if scan.status in ["error", "finished"] and stop_time > datetime.utcnow():
                    # We finished
                    self._finish_monitoring(scan)
                    break
                else:
                    # Not finished, continue polling
                    self._poll(scan)

                # sleep a bit before next poll
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Alert monitor loop error: {exc}")
                await asyncio.sleep(5)

        if self.db:
            self.db.commit()
            self.db.close()


    def _finish_monitoring(self, scan: Scan) -> bool:
        if not self.db:
            return False

        # Scan Info
        if not scan.profile:
            return False
        
        # Cloud Client
        client = self._get_client(scan.profile)
        if not client:
            return False
        
        logger.info("scan %s: Finalizing MDE alert monitoring", scan.id)
        poll_start = scan.created_at

        try:
            processed, with_evidence = self._enrich_alerts_with_evidence(
                scan, client, poll_start
            )
            if processed:
                msg = f"MDE evidence collected for {with_evidence}/{processed} alert(s)"
            else:
                msg = "MDE evidence collection completed (no alerts recorded)"
            db_scan_add_log(self.db, scan, msg)
            logger.info("scan %s - %s", scan.id, msg)
            self.db.commit()
        except Exception as exc:
            logger.error(f"Failed to hydrate MDE evidence for scan {scan.id}: {exc}")
            db_scan_add_log(self.db, scan, f"MDE evidence fetch failed: {exc}")
            # Retry on next loop without auto-closing
            return False

        try:
            self._auto_close(scan, client)
        except Exception as exc:
            logger.error(f"Failed to auto close alerts for scan {scan.id}: {exc}")
            db_scan_add_log(self.db, scan, f"MDE auto-close failed: {exc}")

        self.db.commit()
        return True


    def _poll(self, scan: Scan) -> bool:
        if not self.db:
            return False

        # Scan Info
        if not scan.profile:
            return False
        device_info = scan.profile.data.get("edr_mde", None)
        if not device_info:
            return False
        device_id = device_info.get("device_id", None)
        device_hostname = device_info.get("hostname", None)
        
        # Cloud Client
        client = self._get_client(scan.profile)
        if not client:
            return False

        logger.info("scan %s: Poll for MDE events", scan.id)
 
        # Determine polling window
        since = scan.created_at
        window_end = datetime.utcnow()
        
        try:
            poll_msg = (
                f"MDE poll: profile={scan.profile.name if scan.profile else 'unknown'} "
                f"device_id={device_id} hostname={device_hostname} "
                f"since={since.isoformat()} (window_end={window_end.isoformat()})"
            )
            logger.info("scan %s - %s", scan.id, poll_msg)
            db_scan_add_log(self.db, scan, poll_msg)
            alerts, server_time = client.fetch_alerts(device_id, device_hostname, since)
            server_time_note = f" (MDE server time {server_time})" if server_time else ""
            new_alerts = self._store_alerts(scan, alerts)
            if new_alerts:
                msg = f"MDE alert IDs synced: {len(new_alerts)} new{server_time_note}"
                db_scan_add_log(self.db, scan, msg)
                logger.info("scan %s - %s", scan.id, msg)
                if scan.result not in ("file_detected", "detected"):
                    scan.result = "detected"
                    self.db.commit()
            elif alerts:
                msg = f"MDE poll: {len(alerts)} alert IDs already recorded{server_time_note}"
                logger.info("scan %s - %s", scan.id, msg)
                db_scan_add_log(self.db, scan, msg)
            else:
                msg = f"MDE poll: no alert IDs{server_time_note}"
                logger.info("scan %s - %s", scan.id, msg)
                db_scan_add_log(self.db, scan, msg)
        except Exception as exc:
            logger.error(f"Failed to fetch MDE alerts for scan {scan.id}: {exc}")
            db_scan_add_log(self.db, scan, f"MDE poll failed: {exc}")

        self.db.commit()
        return True


    def _get_client(self, profile: Profile) -> Optional[MDEClient]:
        cfg = profile.data.get("edr_mde") or {}
        if not cfg:
            return None
        cache_key = f"{profile.id}:{cfg.get('client_id')}"
        client = self.client_cache.get(cache_key)
        if client:
            return client
        try:
            client = MDEClient(cfg)
            self.client_cache[cache_key] = client
            return client
        except Exception as exc:
            logger.warning(f"MDE configuration invalid for profile {profile.name}: {exc}")
            return None


    def _store_alerts(self, scan: Scan, alerts: list) -> list:
        new_alerts = []
        existing_ids = {alert.alert_id for alert in scan.alerts}
        for alert in alerts:
            alert_id = alert.get("AlertId") or alert.get("id")
            if not alert_id or alert_id in existing_ids:
                continue
            detected_at = alert.get("Timestamp") or alert.get("lastUpdateTime") or alert.get("eventDateTime")
            detected_dt = None
            if detected_at:
                try:
                    detected_dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
                except ValueError:
                    detected_dt = None
            scan_alert = ScanAlert(
                scan_id=scan.id,
                alert_id=alert_id,
                incident_id=alert.get("incidentId"),
                title=alert.get("Title") or alert.get("title"),
                severity=alert.get("Severity") or alert.get("severity"),
                status=alert.get("status"),
                category=alert.get("Categories") or alert.get("category"),
                detection_source=alert.get("DetectionSource") or alert.get("detectionSource"),
                detected_at=detected_dt,
                raw_alert=alert,
            )
            self.db.add(scan_alert)
            scan.alerts.append(scan_alert)
            new_alerts.append(scan_alert)
        if new_alerts:
            self.db.commit()
        return new_alerts
    

    def _enrich_alerts_with_evidence(
        self,
        scan: Scan,
        client: MDEClient,
        start_time: datetime,
    ) -> Tuple[int, int]:
        alert_ids = [alert.alert_id for alert in scan.alerts if alert.alert_id]
        if not alert_ids:
            return 0, 0

        evidence_rows = client.fetch_alert_evidence(alert_ids, start_time)
        grouped: Dict[str, list] = {}
        for row in evidence_rows:
            alert_id = row.get("AlertId")
            if not alert_id:
                continue
            grouped.setdefault(alert_id, []).append(row)

        processed = 0
        with_evidence = 0
        now_iso = datetime.utcnow().isoformat() + "Z"
        for alert in scan.alerts:
            if not alert.alert_id:
                continue
            processed += 1
            evidence = grouped.get(alert.alert_id, [])
            payload = dict(alert.raw_alert or {})
            payload["AlertId"] = alert.alert_id
            payload["evidence"] = evidence
            payload["evidence_refreshed_at"] = now_iso
            alert.raw_alert = payload
            if evidence:
                with_evidence += 1
                latest = evidence[0]
                ts = latest.get("Timestamp")
                if ts and not alert.detected_at:
                    try:
                        alert.detected_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                alert.title = alert.title or latest.get("ThreatFamilyName") or latest.get("Title")
                alert.category = alert.category or latest.get("Category") or latest.get("Technique") or latest.get("AlertType")
                alert.severity = alert.severity or latest.get("Severity") or latest.get("ReportedSeverity")
                alert.detection_source = alert.detection_source or latest.get("ServiceSource") or latest.get("DetectionSource")
        if processed:
            self.db.commit()
        return processed, with_evidence
    

    def _auto_close(self, scan: Scan, client: MDEClient):
        comment = f"Auto-Closed by Detonator (scan {scan.id})"
        closed_incidents = set()
        for alert in scan.alerts:
            if not alert.auto_closed_at:
                try:
                    client.resolve_alert(alert.alert_id, comment)
                    alert.status = "Resolved"
                    alert.auto_closed_at = datetime.utcnow()
                    alert.comment = comment
                    self.db.commit()
                except Exception as exc:
                    logger.error(f"Failed to resolve alert {alert.alert_id}: {exc}")
            incident_id = alert.incident_id
            if incident_id and incident_id not in closed_incidents:
                try:
                    client.resolve_incident(incident_id, comment)
                    closed_incidents.add(incident_id)
                except Exception as exc:
                    logger.error(f"Failed to resolve incident {incident_id}: {exc}")
        db_scan_add_log(self.db, scan, "Detection window completed. Alerts auto-closed.")
