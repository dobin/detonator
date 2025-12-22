from typing import Optional, Dict, List

from detonatorapi.edr_parser.edr_parser import EdrParser
from detonatorapi.edr_parser.parser_defender import DefenderParser
from detonatorapi.edr_parser.example_parser import ExampleParser


parsers: List[EdrParser] = [
    DefenderParser(),
    ExampleParser(),
]


def get_relevant_edr_parser(edr_telemetry_raw: str) -> Optional[EdrParser]:
    for parser in parsers:
        parser.load(edr_telemetry_raw)
        if parser.is_relevant():
            return parser
    return None
