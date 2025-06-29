import os
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class EDRTemplateManager:
    """Manages EDR templates and deployment scripts"""
    
    def __init__(self):
        self.scripts_dir = Path(__file__).parent / "deployment_scripts"
        self._templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, dict]:
        """Load available EDR templates from the deployment scripts directory"""
        templates = {}
        
        # Define available templates
        template_configs = {
            "openssh": {
                "name": "OpenSSH Server",
                "description": "Installs and configures OpenSSH server for remote access",
                "script_file": "openssh_install.ps1",
                "ports": [22],
                "category": "remote_access"
            },
            "defender": {
                "name": "Windows Defender",
                "description": "Configures Windows Defender with enhanced monitoring",
                "script_file": "defender_config.ps1",
                "ports": [],
                "category": "edr"
            },
            "sysmon": {
                "name": "Sysmon",
                "description": "Installs Sysmon for detailed system monitoring",
                "script_file": "sysmon_install.ps1",
                "ports": [],
                "category": "monitoring"
            },
        }
        
        for template_id, config in template_configs.items():
            script_path = self.scripts_dir / config["script_file"]
            if script_path.exists():
                templates[template_id] = {
                    **config,
                    "script_path": str(script_path),
                    "available": True
                }
            else:
                templates[template_id] = {
                    **config,
                    "script_path": str(script_path),
                    "available": False
                }
                logger.warning(f"Script file not found for template {template_id}: {script_path}")
        
        return templates
    
    def get_available_templates(self) -> List[Dict[str, any]]:
        """Get list of available EDR templates"""
        return [
            {
                "id": template_id,
                **template_info
            }
            for template_id, template_info in self._templates.items()
            if template_info.get("available", False)
        ]
    
    def get_all_templates(self) -> List[Dict[str, any]]:
        """Get list of all EDR templates (including unavailable ones)"""
        return [
            {
                "id": template_id,
                **template_info
            }
            for template_id, template_info in self._templates.items()
        ]
    
    def get_template(self, template_id: str) -> Optional[Dict[str, any]]:
        """Get specific template by ID"""
        if template_id in self._templates:
            return {
                "id": template_id,
                **self._templates[template_id]
            }
        return None
    
    def get_deployment_script(self, template_id: str) -> Optional[str]:
        """Get the deployment script content for a template"""
        template = self.get_template(template_id)
        if not template or not template.get("available"):
            return None
        
        try:
            script_path = Path(template["script_path"])
            if script_path.exists():
                return script_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Error reading script for template {template_id}: {str(e)}")
        
        return None
    
    def get_network_security_rules(self, template_id: str) -> List[Dict[str, any]]:
        """Get additional network security rules required for a template"""
        template = self.get_template(template_id)
        if not template:
            return []
        
        rules = []
        ports = template.get("ports", [])
        
        for i, port in enumerate(ports):
            rules.append({
                'name': f'Allow{template["name"].replace(" ", "")}Port{port}',
                'protocol': 'Tcp',
                'source_port_range': '*',
                'destination_port_range': str(port),
                'source_address_prefix': '*',
                'destination_address_prefix': '*',
                'access': 'Allow',
                'priority': 1100 + i,
                'direction': 'Inbound'
            })
        
        return rules
    
    def validate_template(self, template_id: str) -> bool:
        """Validate that a template exists and is available"""
        template = self.get_template(template_id)
        return template is not None and template.get("available", False)
    
    def reload_templates(self):
        """Reload templates from disk"""
        self._templates = self._load_templates()


# Global EDR template manager instance
edr_manager = EDRTemplateManager()

def get_edr_manager() -> EDRTemplateManager:
    """Get the global EDR template manager instance"""
    return edr_manager
