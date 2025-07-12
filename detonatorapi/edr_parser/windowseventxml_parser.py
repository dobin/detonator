import xml.etree.ElementTree as ET
import pprint


# Remove namespace
def strip_ns(xml):
    return xml.replace("xmlns='http://schemas.microsoft.com/win/2004/08/events/event'", "")


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


def get_xmlevent_data(xml_string):
    if not xml_string or xml_string.strip() == "":
        return []

    root = ET.fromstring(strip_ns(xml_string))
    events = []

    for event in root.findall('Event'):
        parsed_event = parse_windows_event(event)
        event_data = parsed_event.get("EventData", {})

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
        events.append(event)

    return events
