import unittest

from detonatorui.flask_app import from_json_filter


class FromJsonFilterTests(unittest.TestCase):
    def test_decodes_valid_process_output(self):
        result = from_json_filter('{"stdout": "hello", "stderr": "warning"}')

        self.assertEqual(result, {"stdout": "hello", "stderr": "warning"})

    def test_falls_back_to_plain_stdout_for_malformed_json(self):
        result = from_json_filter("plain process output")

        self.assertEqual(result, {"stdout": "plain process output", "stderr": ""})

    def test_falls_back_for_non_object_json(self):
        result = from_json_filter('["unexpected"]')

        self.assertEqual(result, {"stdout": '["unexpected"]', "stderr": ""})

    def test_supplies_missing_output_fields(self):
        result = from_json_filter("{}")

        self.assertEqual(result, {"stdout": "", "stderr": ""})


if __name__ == "__main__":
    unittest.main()