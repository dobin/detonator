import asyncio
import logging
import time
import base64
import os
import yaml
import uuid

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ResourceNotFoundError

from detonatorapi.utils import mylog, scanid_to_vmname
from detonatorapi.database import Scan, get_db


# Set the logging level for Azure SDK loggers to WARNING to reduce verbosity
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

CONFIG_FILE = 'azure.yaml'



unattend_xml = '''
<AutoLogon>
    <Username>rededr</Username>
    <Password>
        <Value>rededr</Value>
        <PlainText>true</PlainText>
    </Password>
    <Enabled>true</Enabled>
    <LogonCount>1</LogonCount>
</AutoLogon>
'''

unattend_xml_oobe = '''
<OOBE>
  <HidePrivacySettings>true</HidePrivacySettings>
</OOBE>
'''

unattend_xml_stuff = '''
<FirstLogonCommands>
    <SynchronousCommand>
        <CommandLine>powershell.exe -EncodedCommand {base64.b64encode(powershell_command.encode('utf-16le')).decode('ascii')}</CommandLine>
        <Order>1</Order>
    </SynchronousCommand>
</FirstLogonCommands>
'''



class AzureManager:
    """Manages Azure VM lifecycle for malware analysis"""
    
    def __init__(self, subscription_id: str, resource_group: str, location: str = "East US"):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.location = location
        self.credential = DefaultAzureCredential()
        
        # Initialize Azure clients
        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)
        self.network_client = NetworkManagementClient(self.credential, self.subscription_id)
        self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)
        

    def create_machine(self, scan_id) -> bool:
        vm_name = scanid_to_vmname(scan_id)
        db = get_db()

        # All required information is in the database entry
        db_scan = db.get(Scan, scan_id)
        if not db_scan:
            logger.error(f"Scan with ID {scan_id} not found in database")
            # No DB to update
            return False
        
        # DB UPDATE: Indicate we creating the VM currently
        db_scan.vm_instance_name = vm_name
        db.commit()
        
        try:
            logger.info(f"Azure: Creating VM: {vm_name} with profile {db_scan.profile.name}")
            logger.info(f"Azure: This can take a few minutes")

            # General VM creation data (check first)
            if 'image_reference' not in db_scan.profile.data or \
                'admin_username' not in db_scan.profile.data or \
                'admin_password' not in db_scan.profile.data:
                logger.error(f"Scan {scan_id} profile data is missing required fields (image_reference, admin_username, admin_password)")
                return False
            image_reference = db_scan.profile.data['image_reference']
            admin_username = db_scan.profile.data['admin_username']
            admin_password = db_scan.profile.data['admin_password']
            
            # Create: network security group with EDR-specific rules
            nsg_name = f"{vm_name}-nsg"
            self._create_network_security_group(nsg_name)
            
            # Create: virtual network and subnet
            vnet_name = f"{vm_name}-vnet"
            subnet_name = f"{vm_name}-subnet"
            self._create_virtual_network(vnet_name, subnet_name)
            
            # Create: public IP
            public_ip_name = f"{vm_name}-ip"
            public_ip = self._create_public_ip(public_ip_name)
            
            # Create: network interface
            nic_name = f"{vm_name}-nic"
            nic = self._create_network_interface(nic_name, vnet_name, subnet_name, public_ip_name, nsg_name)
            
            # Create: the VM with deployment script
            vm_result = self._create_vm(
                vm_name, 
                nic.id, 
                image_reference=image_reference, 
                admin_username=admin_username,
                admin_password=admin_password)
            if not vm_result:
                logger.error(f"Failed to create VM for scan {scan_id}")
                return False
            
            # Get public IP address
            public_ip_info = self.network_client.public_ip_addresses.get(
                self.resource_group, public_ip_name
            )
            logger.info(f"VM {vm_name} created successfully with public IP: {public_ip_info.ip_address}")

            # DB UPDATE: VM details
            db_scan.vm_exist = 1
            db_scan.vm_ip_address = public_ip_info.ip_address
            db_scan.detonator_srv_logs += mylog(f"VM {vm_name} created. IP: {public_ip_info.ip_address}")
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to create VM for scan {scan_id}: {str(e)}")
            return False
        
        return True
    
    
    def _create_network_security_group(self, nsg_name: str):
        """Create network security group with basic rules and EDR-specific rules"""
        # Base security rules
        security_rules = [
            {
                'name': 'AllowRDP',
                'protocol': 'Tcp',
                'source_port_range': '*',
                'destination_port_range': '3389',
                'source_address_prefix': '*',
                'destination_address_prefix': '*',
                'access': 'Allow',
                'priority': 1000,
                'direction': 'Inbound'
            },
            {
                'name': 'AllowHTTP',
                'protocol': 'Tcp',
                'source_port_range': '*',
                'destination_port_range': '80',
                'source_address_prefix': '*',
                'destination_address_prefix': '*',
                'access': 'Allow',
                'priority': 1001,
                'direction': 'Inbound'
            },
            {
                'name': 'Allow8080',
                'protocol': 'Tcp',
                'source_port_range': '*',
                'destination_port_range': '8080',
                'source_address_prefix': '*',
                'destination_address_prefix': '*',
                'access': 'Allow',
                'priority': 1002,
                'direction': 'Inbound'
            }
        ]
        
        nsg_params = {
            'location': self.location,
            'security_rules': security_rules
        }
        
        operation = self.network_client.network_security_groups.begin_create_or_update(
            self.resource_group, nsg_name, nsg_params
        )
        return operation.result()
    

    def _create_virtual_network(self, vnet_name: str, subnet_name: str):
        """Create virtual network and subnet"""
        vnet_params = {
            'location': self.location,
            'address_space': {
                'address_prefixes': ['10.0.0.0/16']
            },
            'subnets': [
                {
                    'name': subnet_name,
                    'address_prefix': '10.0.1.0/24'
                }
            ]
        }
        
        operation = self.network_client.virtual_networks.begin_create_or_update(
            self.resource_group, vnet_name, vnet_params
        )
        return operation.result()
    

    def _create_public_ip(self, public_ip_name: str):
        """Create public IP address"""
        public_ip_params = {
            'location': self.location,
            'public_ip_allocation_method': 'Static',
            'public_ip_address_version': 'IPv4'
        }
        
        operation = self.network_client.public_ip_addresses.begin_create_or_update(
            self.resource_group, public_ip_name, public_ip_params
        )
        return operation.result()
    

    def _create_network_interface(self, nic_name: str, vnet_name: str, subnet_name: str, 
                                       public_ip_name: str, nsg_name: str):
        """Create network interface"""
        subnet = self.network_client.subnets.get(self.resource_group, vnet_name, subnet_name)
        public_ip = self.network_client.public_ip_addresses.get(self.resource_group, public_ip_name)
        nsg = self.network_client.network_security_groups.get(self.resource_group, nsg_name)
        
        nic_params = {
            'location': self.location,
            'ip_configurations': [
                {
                    'name': 'ipconfig1',
                    'subnet': {'id': subnet.id},
                    'public_ip_address': {'id': public_ip.id}
                }
            ],
            'network_security_group': {'id': nsg.id}
        }
        
        operation = self.network_client.network_interfaces.begin_create_or_update(
            self.resource_group, nic_name, nic_params
        )
        return operation.result()
    

    def _create_vm(self, vm_name: str, nic_id: str, image_reference: str, admin_username: str, admin_password: str):
        vm_params = {
            'location': self.location,
            'osProfile': {
                'computerName': vm_name,
                'adminUsername': admin_username,
                'adminPassword': admin_password,
                'windowsConfiguration': {
                    'provision_vm_agent': True,
                    'enable_automatic_updates': True,
                    'additional_unattend_content': [
                        {
                            'pass_name': "oobeSystem",
                            'component_name': "Microsoft-Windows-Shell-Setup",
                            'setting_name': "AutoLogon",
                            'content': unattend_xml
                        }
                        #, 
                        #{
                        #    "pass_name": "oobeSystem",
                        #    "component_name": "Microsoft-Windows-Shell-Setup",
                        #    "setting_name": "OOBE",
                        #    "content": unattend_xml_oobe
                        #}
                    ]
                }
            },
            'hardware_profile': {
                'vm_size': 'Standard_D2s_v3'  # 2 vCPUs, 8 GB RAM
            },
            'storage_profile': {
                'image_reference': {
                    'id': image_reference,
                },
                'os_disk': {
                    'create_option': 'FromImage',
                    'delete_option': 'Delete',  # Delete disk on VM deletion
                    'managed_disk': {
                        'storage_account_type': 'Premium_LRS'
                    }
                }
            },
            'network_profile': {
                'network_interfaces': [
                    {
                        'id': nic_id
                    }
                ]
            },
        }
        
        operation = self.compute_client.virtual_machines.begin_create_or_update(
            self.resource_group, vm_name, vm_params
        )
        return operation.result()
    

    def get_vm_status(self, vm_name: str) -> str:
        """Get the current status of a VM"""
        try:
            vm_instance_view = self.compute_client.virtual_machines.instance_view(
                self.resource_group, vm_name
            )
            
            # Get the power state
            for status in vm_instance_view.statuses:
                if status.code.startswith('PowerState/'):
                    return status.code.replace('PowerState/', '')
            
            return "unknown"
            
        except ResourceNotFoundError:
            return "not_found"
        except Exception as e:
            logger.error(f"Error getting VM status for {vm_name}: {str(e)}")
            return "error"
    

    def shutdown_vm(self, vm_name: str) -> bool:
        """Shutdown and deallocate a VM"""
        try:
            logger.info(f"Shutting down VM: {vm_name}")
            
            # Deallocate the VM (stops and releases compute resources)
            operation = self.compute_client.virtual_machines.begin_deallocate(
                self.resource_group, vm_name
            )
            operation.result()
            
            logger.info(f"VM {vm_name} has been deallocated")
            return True
            
        except ResourceNotFoundError:
            logger.warning(f"VM {vm_name} not found during shutdown")
            return False
        except Exception as e:
            logger.error(f"Error shutting down VM {vm_name}: {str(e)}")
            return False
        
    
    def delete_vm_resources(self, vm_name: str) -> bool:
        """Delete VM and all associated resources, including the OS disk"""
        try:
            logger.info(f"Deleting VM and resources: {vm_name}")
            
            os_disk_name = None

            # Try to get VM to extract OS disk name
            try:
                vm = self.compute_client.virtual_machines.get(self.resource_group, vm_name)
                os_disk_name = vm.storage_profile.os_disk.name
                logger.info(f"Found OS disk: {os_disk_name}")
            except ResourceNotFoundError:
                logger.warning(f"VM {vm_name} not found. Skipping disk lookup.")

            # Delete the VM
            try:
                operation = self.compute_client.virtual_machines.begin_delete(
                    self.resource_group, vm_name
                )
                operation.result()
            except ResourceNotFoundError:
                logger.warning(f"VM {vm_name} not found during delete.")

            # Delete OS disk if we found one
            if os_disk_name:
                try:
                    operation = self.compute_client.disks.begin_delete(
                        self.resource_group, os_disk_name
                    )
                    operation.result()
                    logger.info(f"Deleted OS disk: {os_disk_name}")
                except ResourceNotFoundError:
                    logger.warning(f"OS disk {os_disk_name} not found.")
                except Exception as e:
                    logger.warning(f"Failed to delete OS disk {os_disk_name}: {e}")

            # Delete associated network resources
            resources_to_delete = [
                (self.network_client.network_interfaces, f"{vm_name}-nic"),
                (self.network_client.public_ip_addresses, f"{vm_name}-ip"),
                (self.network_client.network_security_groups, f"{vm_name}-nsg"),
                (self.network_client.virtual_networks, f"{vm_name}-vnet")
            ]
            
            for client, resource_name in resources_to_delete:
                try:
                    if hasattr(client, 'begin_delete'):
                        operation = client.begin_delete(self.resource_group, resource_name)
                        operation.result()
                    else:
                        operation = client.delete(self.resource_group, resource_name)
                        if hasattr(operation, 'result'):
                            operation.result()
                    logger.info(f"Deleted: {resource_name}")
                except ResourceNotFoundError:
                    logger.warning(f"{resource_name} not found.")
                except Exception as e:
                    logger.warning(f"Failed to delete {resource_name}: {str(e)}")
            
            logger.info(f"Successfully deleted VM and resources: {vm_name}")
            return True

        except Exception as e:
            logger.error(f"Error deleting VM resources for {vm_name}: {str(e)}")
            return False
    

    def list_all_vms(self) -> list:
        """List all VMs in the resource group with their status and details"""
        try:
            vms = []
            vm_list = self.compute_client.virtual_machines.list(self.resource_group)
            
            for vm in vm_list:
                if not vm.name:
                    continue
                    
                # Get instance view for power state
                try:
                    instance_view = self.compute_client.virtual_machines.get(
                        self.resource_group, vm.name, expand='instanceView'
                    ).instance_view
                except Exception:
                    instance_view = None
                
                # Extract power state
                power_state = "unknown"
                if instance_view and hasattr(instance_view, 'statuses') and instance_view.statuses:
                    for status in instance_view.statuses:  # type: ignore
                        if hasattr(status, 'code') and status.code and status.code.startswith('PowerState/'):
                            power_state = status.code.replace('PowerState/', '')
                            break
                
                # Get public IP if available
                public_ip = None
                if vm.network_profile and vm.network_profile.network_interfaces:
                    for nic_ref in vm.network_profile.network_interfaces:
                        if nic_ref.id:
                            nic_name = nic_ref.id.split('/')[-1]
                            try:
                                nic = self.network_client.network_interfaces.get(self.resource_group, nic_name)
                                if nic.ip_configurations:
                                    for ip_config in nic.ip_configurations:
                                        if ip_config.public_ip_address and ip_config.public_ip_address.id:
                                            pip_name = ip_config.public_ip_address.id.split('/')[-1]
                                            public_ip_resource = self.network_client.public_ip_addresses.get(
                                                self.resource_group, pip_name
                                            )
                                            public_ip = public_ip_resource.ip_address
                                            break
                            except Exception:
                                pass  # Ignore errors getting public IP
                
                # Extract scan ID from VM name if it follows detonator-{scan_id} pattern
                scan_id = None
                if vm.name and vm.name.startswith('detonator-'):
                    try:
                        scan_id = int(vm.name.split('-')[1])
                    except (IndexError, ValueError):
                        pass
                
                vm_info = {
                    'name': vm.name,
                    'power_state': power_state,
                    'location': vm.location,
                    'vm_size': vm.hardware_profile.vm_size if vm.hardware_profile else None,
                    'public_ip': public_ip,
                    'scan_id': scan_id,
                    'created_time': None  # Azure SDK doesn't always provide creation time
                }
                vms.append(vm_info)
            
            return vms
            
        except Exception as e:
            logger.error(f"Error listing VMs: {str(e)}")
            return []
        

    def stop_and_delete_vm(self, vm_name: str) -> bool:
        """Stop and delete a VM and all its resources"""
        logger.info(f"Stopping and deleting VM: {vm_name}")
        self.shutdown_vm(vm_name)
        self.delete_vm_resources(vm_name)
        return True
          

# Global VM manager instance (will be initialized in main app)
azure_manager: Optional[AzureManager] = None


def read_yaml_config() -> Dict[str, Any]:
    """Read YAML configuration file and return as dictionary"""
    file_path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Error reading YAML config {file_path}: {str(e)}")
        return {}


def initialize_azure_manager():
    """Initialize the global VM manager instance"""
    global azure_manager

    # check if config exists
    if not os.path.exists(CONFIG_FILE):
        logger.info(f"Azure configuration file {CONFIG_FILE} not found. Azure not activated.")
        return True

    config = read_yaml_config()
    required_keys = ['subscription_id', 'resource_group', 'location']
    if not all(key in config for key in required_keys):
        logger.error(f"Azure configuration file {CONFIG_FILE} is missing required keys: {required_keys}")
        return False

    azure_manager = AzureManager(
        subscription_id=config['subscription_id'],
        resource_group=config['resource_group'],
        location=config['location']
    )
    return True


def get_azure_manager() -> AzureManager|None:
    """Get the global VM manager instance"""
    return azure_manager
