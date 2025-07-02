import os
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


template_configs = {
    "new_defender": {
        "type": "new",
        "comment": "",
        "edr_template": "defender",
    },
    "clone_rededr": {
        "type": "clone",
        "comment": "",
        "vm_name": "test-vm",
    },
    "running_rededr": {
        "type": "running",
        "comment": "",
        "ip": "192.168.1.1",
    },
}


class EDRTemplateManager:
    """Manages EDR templates and deployment scripts"""
    
    def __init__(self):
        self.scripts_dir = Path(__file__).parent / "deployment_scripts"
        self._templates = template_configs.copy()
        for template_id, template_info in self._templates.items():
            template_info["id"] = template_id
    

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
    
    
    # Data of templates

    def get_template_deployment_script(self, template_id: str) -> Optional[str]:
        """Get the deployment script content for a template"""
        template = self.get_template(template_id)
        if not template:
            return None
        
        try:
            script_path = Path(template["script_path"])
            if script_path.exists():
                return script_path.read_text(encoding='utf-8')
        except Exception as e:
            #logger.error(f"Error reading script for template {template_id}: {str(e)}")
            # Broken currently anyway
            pass
        
        return None
    
    def get_template_network_security_rules(self, template_id: str):
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
