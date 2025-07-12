from typing import List, Dict


class EdrParser:
    def __init__(self, edr_data: str):
        self.edr_data: str = edr_data

    def parse(self) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

    def get_events(self) -> List[Dict]:
        raise NotImplementedError("Subclasses must implement this method.")
    
    def get_summary(self) -> str:
        raise NotImplementedError("Subclasses must implement this method.")
    
    def is_detected(self) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

