from typing import List, Dict


class EdrParser:
    def __init__(self):
        self.edr_data: str = ""

    def load(self, edr_logs: str):
        self.edr_data = edr_logs
        self.events = []

    def is_relevant(self) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

    def parse(self) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

    def get_events(self) -> List[Dict]:
        raise NotImplementedError("Subclasses must implement this method.")
    
    def get_summary(self) -> str:
        raise NotImplementedError("Subclasses must implement this method.")
    
    def is_detected(self) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

