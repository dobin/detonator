import asyncio
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ResourceNotFoundError
import uuid

logger = logging.getLogger(__name__)

class AzureVMManager:
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
        
    async def create_windows11_vm(self, scan_id: int) -> Dict[str, Any]:
        """Create a Windows 11 VM for malware analysis"""
        vm_name = f"detonator-{scan_id}"
        
        try:
            # Create network security group
            nsg_name = f"{vm_name}-nsg"
            await self._create_network_security_group(nsg_name)
            
            # Create virtual network and subnet
            vnet_name = f"{vm_name}-vnet"
            subnet_name = f"{vm_name}-subnet"
            await self._create_virtual_network(vnet_name, subnet_name)
            
            # Create public IP
            public_ip_name = f"{vm_name}-ip"
            public_ip = await self._create_public_ip(public_ip_name)
            
            # Create network interface
            nic_name = f"{vm_name}-nic"
            nic = await self._create_network_interface(nic_name, vnet_name, subnet_name, public_ip_name, nsg_name)
            
            # Create the VM
            vm_result = await self._create_vm(vm_name, nic.id)
            
            # Get public IP address
            public_ip_info = self.network_client.public_ip_addresses.get(
                self.resource_group, public_ip_name
            )
            
            return {
                "vm_name": vm_name,
                "vm_id": vm_result.id,
                "public_ip": public_ip_info.ip_address,
                "status": "creating",
                "created_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Failed to create VM for scan {scan_id}: {str(e)}")
            raise
    
    async def _create_network_security_group(self, nsg_name: str):
        """Create network security group with basic rules"""
        nsg_params = {
            'location': self.location,
            'security_rules': [
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
                }
            ]
        }
        
        operation = self.network_client.network_security_groups.begin_create_or_update(
            self.resource_group, nsg_name, nsg_params
        )
        return operation.result()
    
    async def _create_virtual_network(self, vnet_name: str, subnet_name: str):
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
    
    async def _create_public_ip(self, public_ip_name: str):
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
    
    async def _create_network_interface(self, nic_name: str, vnet_name: str, subnet_name: str, 
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
    
    async def _create_vm(self, vm_name: str, nic_id: str):
        """Create Windows 11 virtual machine"""
        vm_params = {
            'location': self.location,
            'os_profile': {
                'computer_name': vm_name,
                'admin_username': 'detonator',
                'admin_password': 'DetonatorAnalysis123!',  # Use Azure Key Vault in production
                'windows_configuration': {
                    'enable_automatic_updates': False,
                    'provision_vm_agent': True
                }
            },
            'hardware_profile': {
                'vm_size': 'Standard_D2s_v3'  # 2 vCPUs, 8 GB RAM
            },
            'storage_profile': {
                'image_reference': {
                    'publisher': 'MicrosoftWindowsDesktop',
                    'offer': 'Windows-11',
                    'sku': 'win11-24h2-pro',
                    'version': 'latest'
                },
                'os_disk': {
                    'create_option': 'FromImage',
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
            }
        }
        
        operation = self.compute_client.virtual_machines.begin_create_or_update(
            self.resource_group, vm_name, vm_params
        )
        return operation.result()
    
    async def get_vm_status(self, vm_name: str) -> str:
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
    
    async def shutdown_vm(self, vm_name: str) -> bool:
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
    
    async def delete_vm_resources(self, vm_name: str) -> bool:
        """Delete VM and all associated resources"""
        try:
            logger.info(f"Deleting VM and resources: {vm_name}")
            
            # Delete VM
            try:
                operation = self.compute_client.virtual_machines.begin_delete(
                    self.resource_group, vm_name
                )
                operation.result()
            except ResourceNotFoundError:
                pass
            
            # Delete associated resources
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
                except ResourceNotFoundError:
                    pass
                except Exception as e:
                    logger.warning(f"Failed to delete {resource_name}: {str(e)}")
            
            logger.info(f"Successfully deleted VM and resources: {vm_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting VM resources for {vm_name}: {str(e)}")
            return False


# Global VM manager instance (will be initialized in main app)
vm_manager: Optional[AzureVMManager] = None

def initialize_vm_manager(subscription_id: str, resource_group: str, location: str = "East US"):
    """Initialize the global VM manager instance"""
    global vm_manager
    vm_manager = AzureVMManager(subscription_id, resource_group, location)
    return vm_manager

def get_vm_manager() -> AzureVMManager:
    """Get the global VM manager instance"""
    if vm_manager is None:
        raise RuntimeError("VM Manager not initialized. Call initialize_vm_manager() first.")
    return vm_manager
