from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET
import logging
import json
import urllib.parse
from .edr_parser import EdrParser

logger = logging.getLogger(__name__)

from .edr_parser import EdrParser
from detonatorapi.database import get_db_direct, Submission, SubmissionAlert, Profile


class ExampleParser(EdrParser):
    @staticmethod
    def is_relevant(edr_data: str) -> bool:
        return 'SuperMegaEdrAlert' in edr_data
    
    @staticmethod
    def parse(edr_data: str) -> Tuple[bool, List[SubmissionAlert], bool]:
        alerts: List[SubmissionAlert] = []
        try:
            data = json.loads(edr_data)
            for alert_entry in data.get("alerts", []):
                alert = SubmissionAlert(
                    title=alert_entry.get("title", "Example EDR Alert"),
                    severity=alert_entry.get("severity", "Medium"),
                    source=alert_entry.get("source", "ExampleEDR"),
                    category=alert_entry.get("category", "Malware"),
                    detection_source=alert_entry.get("detection_source", "EDR"),
                    detected_at=alert_entry.get("detected_at"),
                )
                alerts.append(alert)
            return True, alerts, False
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse EDR data as JSON: {e}")
            return False, [], False
