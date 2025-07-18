#!/usr/bin/env python3
"""
Migration script to convert profiles_init.yaml to database profiles
"""

import yaml
import logging

from detonatorapi.database import get_db_for_thread
from detonatorapi.db_interface import db_create_profile, db_get_profile_by_name

logger = logging.getLogger(__name__)


def initialize_profiles_from_yaml(db, yaml_data: dict):
    """Initialize profiles from YAML data structure"""
    for profile_name, profile_config in yaml_data.items():
        # Check if profile already exists
        existing_profile = db_get_profile_by_name(db, profile_name)
        if existing_profile:
            logger.info(f"Profile '{profile_name}' already exists, skipping")
            continue
            
        # Create new profile
        db_create_profile(
            db=db,
            name=profile_name,
            connector=profile_config.get('connector', ''),
            port=profile_config.get('port', 80),
            edr_collector=profile_config.get('edr_collector', ''),
            data=profile_config.get('data', {}),
            comment=profile_config.get('comment', ''),
            password=profile_config.get('password', '')
        )
        logger.info(f"Initialized profile '{profile_name}' from YAML")


def load_yaml_config(file_path: str) -> dict:
    """Load YAML configuration file"""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def main():
    # Load the YAML data
    yaml_data = load_yaml_config('profiles_init.yaml')
    
    # Get database session
    db = get_db_for_thread()
    
    try:
        # Initialize profiles from YAML
        initialize_profiles_from_yaml(db, yaml_data)
        print("Successfully migrated profiles_init.yaml to database profiles")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
