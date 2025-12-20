from typing import Dict, List
import xml.etree.ElementTree as ET
import logging
import json
import urllib.parse
from .edr_parser import EdrParser

logger = logging.getLogger(__name__)


class ExampleParser(EdrParser):
    def __init__(self):
        pass


    def load(self, edr_logs: str):
        pass


    def is_relevant(self) -> bool:
        return False


    def parse(self) -> bool:
        return True
    

    def get_events(self) -> List[Dict]:
        return []
    

    def get_summary(self) -> List[Dict]:
        return []


    def is_detected(self) -> bool:
        return False
