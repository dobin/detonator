from typing import Dict, List
import xml.etree.ElementTree as ET
import logging
import json
import urllib.parse
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
        self.events = []
        self.edr_data = edr_logs


    def is_relevant(self) -> bool:
        #return 'http://schemas.microsoft.com/win/2004/08/events/event' in self.edr_data
        return '<Events>' in self.edr_data


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
            if not 'Threat ID' in event_data:
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

            # check if we didnt already have this event in self.events
            if not any(e.get('threat_name') == threat_name for e in self.events):
                self.events.append(event)
                                                                 
        return True
    

    def get_events(self) -> List[Dict]:
        return self.events
    

    def get_summary(self) -> List[Dict]:
        edr_summary: List[Dict] = []

        if len(self.events) == 0:
            return []

        for event in self.events:
            # Behavior:Win32/Meterpreter.gen!A
            threat_name_short = event.get('threat_name', '')
            if ':' in threat_name_short:
                threat_name_short = threat_name_short.split(':', 1)[1].strip()
            threat_name_short_urlencoded = urllib.parse.quote(threat_name_short)
            url = f"https://defendersearch.r00ted.ch/search?threat_name={threat_name_short_urlencoded}"

            summary_entry = {
                "name": event.get('threat_name', '?'),
                "severity": event.get('severity_name', '?'),
                "url": url
            }
            edr_summary.append(summary_entry)
        return edr_summary


    def is_detected(self) -> bool:
        return 'Suspicious' in self.edr_data or 'Threat ID' in self.edr_data
