from typing import List, Dict


class EdrParser:
    def __init__(self):
        self.edr_data: str = ""

    def load(self, edr_telemetry_raw: str):
        self.edr_data = edr_telemetry_raw
        self.events = []

    def is_relevant(self) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

    def parse(self) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

    def get_raw_events(self) -> List[Dict]:
        raise NotImplementedError("Subclasses must implement this method.")
    
    def get_edr_alerts(self) -> List[Dict]:
        raise NotImplementedError("Subclasses must implement this method.")
    
    def is_detected(self) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

