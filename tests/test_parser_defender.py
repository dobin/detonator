import logging
import unittest
from typing import Optional, Dict, List, Type
import datetime

from detonatorapi.edr_parser.parser_defender import DefenderParser
from detonatorapi.settings import UPLOAD_DIR, AGENT_DATA_GATHER_INTERVAL
from detonatorapi.database import Submission, SubmissionAlert, get_db_direct
from detonatorapi.edr_parser.edr_parser_manager import EdrParser, get_relevant_edr_parser


class TestParserDefender(unittest.TestCase):
    def test_parser_defender(self):
        with open("tests/data/defender_result.xml", "r") as file:
            edr_telemetry_raw = file.read()

        edr_parser: Optional[Type[EdrParser]] = get_relevant_edr_parser(edr_telemetry_raw)
        self.assertIsNotNone(edr_parser, "DefenderParser should be recognized as relevant parser.")
        self.assertEqual(edr_parser, DefenderParser, "The relevant parser should be DefenderParser.")

        ok, alerts, is_detected = edr_parser.parse(edr_telemetry_raw)
        self.assertTrue(ok, "Parsing should complete successfully.")
        self.assertTrue(is_detected, "A detection should be found in the telemetry.")
        self.assertGreater(len(alerts), 0, "At least one alert should be generated.")
        first_alert: SubmissionAlert = alerts[0]
        self.assertEqual(first_alert.alert_id, "{6029D8AE-A305-41BD-9BF4-4378168C91C0}", "Alert ID should match expected value.")
        self.assertEqual(first_alert.title, "Behavior:Win32/Meterpreter.gen!A", "Alert title should match expected value.")
        self.assertEqual(first_alert.severity, "Severe", "Alert severity should match expected value.")
        self.assertEqual(first_alert.category, "Suspicious Behaviour", "Alert category should match expected value.")
        self.assertEqual(first_alert.detected_at, datetime.datetime(2025, 7, 12, 18, 45, 56, 925000, tzinfo=datetime.timezone.utc), "Alert detected_at should match expected value.") 