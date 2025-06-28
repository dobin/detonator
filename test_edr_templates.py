#!/usr/bin/env python3
"""
Test script for EDR template functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_edr_templates():
    """Test EDR template functionality"""
    print("Testing EDR Template Manager...")
    print("=" * 50)
    
    try:
        from detonator.edr_templates import get_edr_manager
        
        # Get the manager
        edr_manager = get_edr_manager()
        print("✅ EDR Manager initialized successfully")
        
        # Get all templates
        all_templates = edr_manager.get_all_templates()
        print(f"📋 Found {len(all_templates)} total templates:")
        
        for template in all_templates:
            status = "✅ Available" if template["available"] else "❌ Script Missing"
            print(f"  - {template['id']}: {template['name']} - {status}")
            print(f"    Description: {template['description']}")
            print(f"    Category: {template['category']}")
            print(f"    Ports: {template['ports']}")
            print()
        
        # Get available templates
        available_templates = edr_manager.get_available_templates()
        print(f"✅ {len(available_templates)} templates are available for use")
        
        # Test specific template
        if available_templates:
            test_template = available_templates[0]
            template_id = test_template["id"]
            print(f"\nTesting template: {template_id}")
            
            # Get deployment script
            script = edr_manager.get_deployment_script(template_id)
            if script:
                print(f"✅ Deployment script loaded ({len(script)} characters)")
                print(f"Script preview: {script[:200]}...")
            else:
                print("❌ Failed to load deployment script")
            
            # Get security rules
            rules = edr_manager.get_network_security_rules(template_id)
            print(f"🔒 Generated {len(rules)} network security rules")
            for rule in rules:
                print(f"  - {rule['name']}: Port {rule['destination_port_range']}")
        
        print("\n" + "=" * 50)
        print("✅ EDR Template functionality test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_edr_templates()
    sys.exit(0 if success else 1)
