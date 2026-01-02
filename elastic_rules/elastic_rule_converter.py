#!/usr/bin/env python3
"""
Script to parse Elastic detection rule TOML files and extract rule IDs.
Outputs a CSV file with rule_id and filepath.
"""

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python versions

from pathlib import Path
import csv


class ElasticRuleResolver:
    def __init__(self, csv_path: str = "elastic_rules.csv"):
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
    

def parse_elastic_rules(rules_dir: str, output_csv: str = "elastic_rules.csv"):
    """
    Parse TOML files in the given directory and extract rule_id.
    
    Args:
        rules_dir: Path to the directory containing subdirectories with TOML files
        output_csv: Output CSV filename
    """
    rules_path = Path(rules_dir)
    
    if not rules_path.exists():
        print(f"Error: Directory {rules_dir} does not exist")
        print("Please clone the Elastic detection-rules repository from:")
        print("https://github.com/elastic/detection-rules/")
        return
    
    # Find all subdirectories, excluding those starting with underscore
    subdirs = [d for d in rules_path.iterdir() if d.is_dir() and not d.name.startswith('_')]
    
    if not subdirs:
        print(f"No subdirectories found in {rules_dir}")
        return
    
    print(f"Found {len(subdirs)} subdirectories to process: {', '.join(d.name for d in subdirs)}")
    
    # Find all TOML files in all subdirectories
    toml_files = []
    for subdir in subdirs:
        toml_files.extend(list(subdir.glob("*.toml")))
    
    if not toml_files:
        print(f"No TOML files found in {rules_dir}")
        return
    
    print(f"Found {len(toml_files)} TOML files")
    
    # Parse files and collect rule_id and filepath
    results = []
    errors = []
    
    for toml_file in toml_files:
        try:
            with open(toml_file, 'rb') as f:
                data = tomllib.load(f)
                
            # Extract rule_id from [rule] section
            if 'rule' in data and 'rule_id' in data['rule']:
                rule_id = data['rule']['rule_id']
                results.append((rule_id, str(toml_file)))
            else:
                errors.append(f"No rule_id found in {toml_file}")
                
        except Exception as e:
            errors.append(f"Error parsing {toml_file}: {e}")
    
    # Write to CSV
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')
        writer.writerow(['rule_id', 'filepath'])
        for rule_id, filepath in sorted(results):
            writer.writerow([rule_id, filepath])
    
    print(f"\nSuccessfully parsed {len(results)} rules")
    print(f"Output written to {output_csv}")
    
    if errors:
        print(f"\nEncountered {len(errors)} errors:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")


if __name__ == "__main__":
    import sys
    
    # Default to rules directory
    rules_dir = "detection-rules/rules/"
    
    # Allow override from command line
    if len(sys.argv) > 1:
        rules_dir = sys.argv[1]
    
    output_csv = "elastic_rules.csv"
    if len(sys.argv) > 2:
        output_csv = sys.argv[2]
    
    print(f"Parsing rules from: {rules_dir}")
    parse_elastic_rules(rules_dir, output_csv)
