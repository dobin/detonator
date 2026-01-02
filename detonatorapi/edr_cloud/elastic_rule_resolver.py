
from pathlib import Path
import csv


class ElasticRuleResolver:
    def __init__(self, csv_path: str = "elastic_rules/elastic_rules.csv"):
        self.csv_path = csv_path
        self.rule_map = {}
        self._load_rules()
    
    def _load_rules(self):
        """Load rules from CSV file into memory."""
        try:
            with open(self.csv_path, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                for row in reader:
                    rule_id = row['rule_id']
                    filepath = row['filepath']
                    self.rule_map[rule_id] = filepath
            print(f"Loaded {len(self.rule_map)} rules from {self.csv_path}")
        except FileNotFoundError:
            print(f"Error: CSV file {self.csv_path} not found")
        except Exception as e:
            print(f"Error loading CSV: {e}")
    
    def get_path(self, rule_id: str) -> str | None:
        return self.rule_map.get(rule_id)
    
    def has_rule(self, rule_id: str) -> bool:
        return rule_id in self.rule_map
    