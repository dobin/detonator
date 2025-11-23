import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import pprint

from sqlalchemy.orm import Session, joinedload

from ..database import get_db, Scan, ScanAlert, Profile
from .mde_client import MDEClient
from ..db_interface import db_scan_add_log, db_scan_change_status_quick

logger = logging.getLogger(__name__)

POLLING_TIME_MINUTES = 10  # post 


class AlertMonitorMde:

    def __init__(self, scan_id: int):
        self.scan_id = scan_id
        self.task: Optional[asyncio.Task] = None
        self.db: Optional[Session] = None
        self.client_cache: Dict[str, MDEClient] = {}


    def start_monitoring(self):
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("Alert monitoring task started")


    async def _monitor_loop(self):
        self.db = get_db()

        #start_time = datetime.utcnow()
        #while start_time + timedelta(minutes=POLLING_TIME_MINUTES) > datetime.utcnow():
        while True:
            try:
                scan = self.db.query(Scan).filter(Scan.id == self.scan_id).first()
                if not scan:
                    break
                
                # check if we are done
                if scan.status in ("error", "finished"):
                    # check if we are > POLLING_TIME_MINUTES after completed_at
                    if scan.completed_at and \
                          scan.completed_at + timedelta(minutes=POLLING_TIME_MINUTES) < datetime.utcnow():
                        break

                # poll
                self._poll(scan)

                # sleep a bit before next poll
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Alert monitor loop error: {exc}")
                await asyncio.sleep(5)

        # We finished. Close alerts
        scan = self.db.query(Scan).filter(Scan.id == self.scan_id).first()
        if scan:
            self._finish_monitoring(scan)

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
        time_from = scan.created_at
        time_to = scan.completed_at or datetime.utcnow()
        
        try:
            poll_msg = f"MDE poll {scan.id}: from {time_from.isoformat()} to {time_to.isoformat()} "
            db_scan_add_log(self.db, scan, poll_msg)

            alerts = client.fetch_alerts(
                device_id, device_hostname, time_from, time_to
            )
            #pprint.pprint(alerts)
            self._store_alerts(scan, alerts)
        except Exception as exc:
            db_scan_add_log(self.db, scan, f"MDE poll: failed: {exc}")

        self.db.commit()
        return True


    def _store_alerts(self, scan: Scan, alerts_with_evidence):
        """Store alerts with their evidence already included."""
        existing_ids = {alert.alert_id for alert in scan.alerts}
        
        for alert in alerts_with_evidence:
            alert_id = alert.get("AlertId", None)
            if not alert_id:
                continue
            if alert_id in existing_ids:
                continue

            # somehow we have a lot of duplicates in the list?
            existing_ids.add(alert_id)

            # Extract metadata from first evidence row
            detected_at = alert.get("Timestamp")
            detected_dt = None
            if detected_at:
                try:
                    detected_dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
                except ValueError:
                    detected_dt = None
            
            scan_alert = ScanAlert(
                scan_id=scan.id,
                alert_id=alert_id,
                title=alert.get("Title"),
                severity=alert.get("Severity"),
                category=alert.get("Categories"),
                detection_source=alert.get("DetectionSource"),
                detected_at=detected_dt,
            )
            self.db.add(scan_alert)
            scan.alerts.append(scan_alert)
            logger.info(f"scan {scan.id}: New alert stored: {alert_id}")
            
        self.db.commit()
    

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