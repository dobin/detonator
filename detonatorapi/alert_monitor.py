import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session, joinedload

from .database import get_db_for_thread, Scan, ScanAlert, Profile
from .mde_client import MDEClient
from .db_interface import db_scan_add_log, db_scan_change_status_quick

logger = logging.getLogger(__name__)


class AlertMonitorTask:
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.db: Optional[Session] = None
        self.client_cache: Dict[str, MDEClient] = {}

    def start_monitoring(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("Alert monitoring task started")

    def stop_monitoring(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                self.task
            except asyncio.CancelledError:
                pass
        logger.info("Alert monitoring task stopped")

    async def _monitor_loop(self):
        self.db = get_db_for_thread()
        while self.running:
            try:
                self.check_scans()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Alert monitor loop error: {exc}")
                await asyncio.sleep(5)

        if self.db:
            self.db.commit()
            self.db.close()

    def _get_client(self, profile: Profile) -> Optional[MDEClient]:
        cfg = profile.mde or {}
        if not cfg:
            return None
        cache_key = f"{profile.id}:{cfg.get('client_id')}:{cfg.get('client_secret_env')}"
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

    def check_scans(self):
        if not self.db:
            return
        scans = (
            self.db.query(Scan)
            .options(joinedload(Scan.profile), joinedload(Scan.alerts))
            .filter(Scan.device_id.isnot(None))
            .all()
        )
        now = datetime.utcnow()
        for scan in scans:
            options = dict(scan.more_options or {})
            if options.get("mde_monitor_done"):
                continue
            if not scan.profile or not scan.profile.mde:
                continue
            client = self._get_client(scan.profile)
            if not client:
                continue
            if scan.completed_at is None:
                continue

            window_minutes = scan.detection_window_minutes or 0
            window_end = scan.completed_at + timedelta(minutes=window_minutes)

            # If detection window is over, finalize and skip polling
            if now >= window_end:
                if not options.get("mde_monitor_done"):
                    try:
                        self._auto_close(scan, client)
                    except Exception as exc:
                        logger.error(f"Failed to auto close alerts for scan {scan.id}: {exc}")
                        db_scan_add_log(self.db, scan, f"MDE auto-close failed: {exc}")
                    options["mde_monitor_done"] = True
                    scan.more_options = options
                    if scan.status == "polling":
                        db_scan_change_status_quick(self.db, scan, "finished")
                    self.db.commit()
                continue

            # Determine polling window
            base_since = scan.created_at or scan.completed_at or datetime.utcnow()
            last_poll_iso = options.get("mde_last_poll")
            if last_poll_iso:
                try:
                    since = datetime.fromisoformat(last_poll_iso)
                except ValueError:
                    since = base_since
                else:
                    if since < base_since:
                        since = base_since
            else:
                since = base_since

            try:
                poll_msg = (
                    f"MDE poll: profile={scan.profile.name if scan.profile else 'unknown'} "
                    f"device_id={scan.device_id} hostname={scan.device_hostname} "
                    f"since={since.isoformat()} window_end={window_end.isoformat()}"
                )
                logger.info("scan %s - %s", scan.id, poll_msg)
                db_scan_add_log(self.db, scan, poll_msg)
                alerts, server_time = client.fetch_alerts(scan.device_id, scan.device_hostname, since, window_end)
                server_time_note = f" (MDE server time {server_time})" if server_time else ""
                new_alerts = self._store_alerts(scan, alerts)
                if new_alerts:
                    msg = f"MDE alerts synced: {len(new_alerts)} new{server_time_note}"
                    db_scan_add_log(self.db, scan, msg)
                    logger.info("scan %s - %s", scan.id, msg)
                    if scan.result not in ("file_detected", "detected"):
                        scan.result = "detected"
                        self.db.commit()
                elif alerts:
                    msg = f"MDE poll: {len(alerts)} alerts already recorded{server_time_note}"
                    logger.info("scan %s - %s", scan.id, msg)
                    db_scan_add_log(self.db, scan, msg)
                else:
                    msg = f"MDE poll: no alerts{server_time_note}"
                    logger.info("scan %s - %s", scan.id, msg)
                    db_scan_add_log(self.db, scan, msg)
                options["mde_last_poll"] = datetime.utcnow().isoformat()
            except Exception as exc:
                logger.error(f"Failed to fetch MDE alerts for scan {scan.id}: {exc}")
                db_scan_add_log(self.db, scan, f"MDE poll failed: {exc}")
                options["mde_monitor_done"] = True
                scan.more_options = options
                if scan.status == "polling":
                    db_scan_change_status_quick(self.db, scan, "finished")
                self.db.commit()
                continue

            scan.more_options = options
            self.db.commit()

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


alert_monitor = AlertMonitorTask()


def start_alert_monitoring():
    alert_monitor.start_monitoring()


def stop_alert_monitoring():
    alert_monitor.stop_monitoring()
