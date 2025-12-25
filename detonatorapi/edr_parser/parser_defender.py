from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET
import logging
import json
import urllib.parse
from datetime import datetime

from .edr_parser import EdrParser
from detonatorapi.database import get_db_direct, Submission, SubmissionAlert, Profile

logger = logging.getLogger(__name__)


# <Event>
#   <System>
#   <EventData>
#      <Data>
#
# For more details, see test_parser_defender.py
#
def parse_windows_event(event):
    data = {}
    system = event.find('System')
    if system is not None:
        data['System'] = {child.tag: child.text or child.attrib for child in system}
    eventdata = event.find('EventData')
    if eventdata is not None:
        data['EventData'] = {
            d.attrib['Name']: d.text for d in eventdata.findall('Data') if 'Name' in d.attrib
        }
    return data


class DefenderParser(EdrParser):
    @staticmethod
    def is_relevant(edr_data: str) -> bool:
        #return 'http://schemas.microsoft.com/win/2004/08/events/event' in self.edr_data
        return '<Events>' in edr_data

    @staticmethod
    def parse(edr_data: str) -> Tuple[bool, List[SubmissionAlert], bool]:
        if not edr_data or edr_data.strip() == "":
            logger.warning("No XML data provided for parsing.")
            return False, [], False
    
        # parse the XML
        # important
        edr_data = edr_data.replace("xmlns='http://schemas.microsoft.com/win/2004/08/events/event'", "")
        xml_root = ET.fromstring(edr_data)

        alerts: List[SubmissionAlert] = []
        for xml_event in xml_root.findall('Event'):
            parsed_event: Dict = parse_windows_event(xml_event)
            event_data = parsed_event.get("EventData", {})

            # Make sure we have a detection
            if not 'Threat ID' in event_data:
                continue

            detection_id = event_data.get("Detection ID", "Unknown")
            category_name = event_data.get("Category Name", "Unknown")
            detection_time_str = event_data.get("Detection Time", "Unknown")
            severity_name = event_data.get("Severity Name", "Unknown")
            threat_name = event_data.get("Threat Name", "Unknown")
            source_name = event_data.get("Source Name", "Unknown")

            # Convert detection time to datetime object
            detection_time: datetime | None = None
            if detection_time_str != "Unknown":
                try:
                    # Parse ISO 8601 format: 2025-07-04T14:55:37.511Z
                    detection_time = datetime.fromisoformat(detection_time_str.replace('Z', '+00:00'))
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Failed to parse detection time '{detection_time_str}': {e}")
                    detection_time = None

            submission_alert = SubmissionAlert(
                submission_id = 0,
                source = "Defender Local Plugin",
                raw = json.dumps(event_data),
                
                alert_id = detection_id,
                title = threat_name,
                severity = severity_name,
                category = category_name,

                detection_source = source_name,
                detected_at = detection_time,
                additional_data = {},
            )
            alerts.append(submission_alert)

        is_detected = False
        if 'Suspicious' in edr_data or 'Threat ID' in edr_data:
            is_detected = True

        return True, alerts, is_detected
