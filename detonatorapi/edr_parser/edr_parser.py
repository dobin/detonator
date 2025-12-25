from typing import List, Dict, Tuple

from detonatorapi.database import SubmissionAlert


class EdrParser:
    @staticmethod
    def is_relevant(edr_data: str) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

    @staticmethod
    def parse(edr_data: str) -> Tuple[bool, List[SubmissionAlert], bool]:
        raise NotImplementedError("Subclasses must implement this method.")
