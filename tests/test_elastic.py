from unittest import TestCase
import json

from detonatorapi.edr_cloud.elastic_cloud_plugin import CloudElasticPlugin


class TestElastic(TestCase):
    def test_parser(self):
        elasticCloudPlugin = CloudElasticPlugin()

        with open("tests/elastic_data.json", "r") as f:
            elastic_data = json.load(f)

        alerts = elasticCloudPlugin.convert_elastic_alerts(elastic_data)
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)

        first_alert = alerts[0]
        self.assertIsInstance(first_alert, dict)
        self.assertEqual(first_alert.get("alert_id"), "dd3f01efa6c30e6e2c869414dd07b8764b09341f33d269f6c2a64c35786c216f")
        self.assertEqual(first_alert.get("severity"), "medium")    
        self.assertEqual(first_alert.get("detection_source"), "Endpoint process event")
        self.assertEqual(first_alert.get("detected_at"), "2026-01-01T09:33:44.088Z")

        self.assertEqual(first_alert["additional_data"].get("rule_id"), "ebfe1448-7fac-4d59-acea-181bd89b1f7f")
        
