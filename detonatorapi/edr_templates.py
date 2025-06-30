import os
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


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


class EDRTemplateManager:
    """Manages EDR templates and deployment scripts"""
    
    def __init__(self):
        self.scripts_dir = Path(__file__).parent / "deployment_scripts"
        self._templates = template_configs
        for template_id, template_info in self._templates.items():
            template_info["id"] = template_id
    

    def has_template(self, template_id: str) -> bool:
        if template_id in self._templates:
            return True
        return False
    

    def get_templates(self) -> List[Dict[str, any]]:
        return self._templates
    
    
    def get_template(self, template_id: str) -> Optional[Dict[str, any]]:
        if template_id in self._templates:
            return self._templates[template_id]
        return None
    
    
    # Data of templates

    def get_template_deployment_script(self, template_id: str) -> Optional[str]:
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
    
    def get_template_network_security_rules(self, template_id: str) -> List[Dict[str, any]]:
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


# Global EDR template manager instance
edr_template_manager = EDRTemplateManager()

def get_edr_template_manager() -> EDRTemplateManager:
    """Get the global EDR template manager instance"""
    return edr_template_manager
