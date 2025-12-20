import logging
import unittest
from detonatorapi.edr_parser.parser_defender import DefenderParser


class TestParserDefender(unittest.TestCase):
    def test_parser_defender(self):
        with open("tests/data/defender_result.xml", "r") as file:
            edr_telemetry_raw = file.read()
        parser = DefenderParser()
        parser.load(edr_telemetry_raw)
        self.assertTrue(parser.is_relevant(), "Parser should be relevant for Defender logs")
        parser.parse()
        self.assertEqual(len(parser.events), 7, "Expected one event in the parsed data")
        self.assertEqual(parser.events[0]['category_name'], "Suspicious Behaviour", "Expected category name to be 'Malware'")
