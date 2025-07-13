import os
import logging
from typing import Dict, List, Optional
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


class EDRTemplateManager:
    """Manages EDR templates and deployment scripts"""
    
    def __init__(self):
        self._templates: Dict[str, Dict] = {}


    def load_templates(self) -> bool:
        templates_file = "edr_templates.yaml"
        try:
            with open(templates_file, 'r', encoding='utf-8') as f:
                self._templates = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading EDR templates from {templates_file}: {str(e)}")
            return False

        for template_id, template_info in self._templates.items():
            template_info["id"] = template_id

        logger.info(f"Loaded {len(self._templates)} EDR templates from {templates_file}")
        return True
    

    def has_template(self, template_id: str) -> bool:
        if template_id in self._templates:
            return True
        return False
    

    def get_templates(self):
        return list(self._templates.values())
    
    
    def get_template(self, template_id: str):
        if template_id in self._templates:
            return self._templates[template_id]
        return None
    
# Global EDR template manager instance
edr_template_manager = EDRTemplateManager()

