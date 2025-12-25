from typing import Optional, Dict, List, Type

from detonatorapi.edr_parser.edr_parser import EdrParser
from detonatorapi.edr_parser.parser_defender import DefenderParser
from detonatorapi.edr_parser.example_parser import ExampleParser


parsers: List[Type[EdrParser]] = [
    DefenderParser,
    ExampleParser,
]


def get_relevant_edr_parser(edr_telemetry_raw: str) -> Optional[Type[EdrParser]]:
    for parser in parsers:
        if parser.is_relevant(edr_telemetry_raw):
            return parser

    return None
