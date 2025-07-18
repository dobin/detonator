from typing import Dict, List
import xml.etree.ElementTree as ET
import logging
import json

from .edr_parser import EdrParser

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
    def __init__(self):
        self.edr_data = ""
        self.events: List[Dict] = []  # by self.parse()


    def load(self, edr_logs: str):
        xml_events: str = ""
        try:
            edr_logs_obj: Dict = json.loads(edr_logs)
            xml_events = edr_logs_obj.get("xml_events", "")
        except Exception as e:
            logger.error(edr_logs)
            logger.error(f"Error parsing Defender XML logs: {e}")

        self.edr_data = xml_events


    def is_relevant(self) -> bool:
        return 'http://schemas.microsoft.com/win/2004/08/events/event' in self.edr_data


    def parse(self) -> bool:
        xml_string: str = self.edr_data
        if not xml_string or xml_string.strip() == "":
            logger.warning("No XML data provided for parsing.")

        # important
        xml_string = xml_string.replace("xmlns='http://schemas.microsoft.com/win/2004/08/events/event'", "")

        # parse the XML
        xml_root = ET.fromstring(xml_string)
        for xml_event in xml_root.findall('Event'):
            parsed_event: Dict = parse_windows_event(xml_event)
            event_data = parsed_event.get("EventData", {})

            # Make sure we have a detection
            if not 'Thread ID' in event_data:
                continue

            category_name = event_data.get("Category Name", "Unknown")
            detection_time = event_data.get("Detection Time", "Unknown")
            engine_version = event_data.get("Engine Version", "Unknown")
            detection_time = event_data.get("Detection Time", "Unknown")
            detection_user = event_data.get("Detection User", "Unknown")
            product_version = event_data.get("Product Version", "Unknown")
            severity_id = event_data.get("Severity ID", "Unknown")
            severity_name = event_data.get("Severity Name", "Unknown")
            threat_id = event_data.get("Threat ID", "Unknown")
            threat_name = event_data.get("Threat Name", "Unknown")
            type_id = event_data.get("Type ID", "Unknown")
            type_name = event_data.get("Type Name", "Unknown")
            path = str(event_data.get("Path", "Unknown"))
            event = {
                "category_name": category_name,
                "detection_time": detection_time,
                "engine_version": engine_version,
                "detection_user": detection_user,
                "product_version": product_version,
                "severity_id": severity_id,
                "severity_name": severity_name,
                "threat_id": threat_id,
                "threat_name": threat_name,
                "type_id": type_id,
                "type_name": type_name,
                "path": path,
            }
            self.events.append(event)

        return True
    

    def get_events(self) -> List[Dict]:
        return self.events
    

    def get_summary(self) -> str:
        edr_summary: List[str] = []
        for event in self.events:
            e = f"{event.get('threat_name', '?')}: {event.get('severity_name', '?')}"
            edr_summary.append(e)
        return "\n".join(edr_summary)


    def is_detected(self) -> bool:
        return 'Suspicious' in self.edr_data
