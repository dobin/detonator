from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import logging

from .connectors.azure_manager import get_azure_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/vms")
async def get_vms():
    """Get all VMs in the resource group"""
    try:
        azure_manager = get_azure_manager()
        if not azure_manager:
            return {}
        vms = azure_manager.list_all_vms()
        return vms
    except Exception as e:
        logger.error(f"Error getting VMs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get VMs: {str(e)}")


@router.delete("/vms/{vm_name}")
async def delete_vm(vm_name: str, background_tasks: BackgroundTasks):
    """Stop and delete a VM and all its resources"""
    try:
        azure_manager = get_azure_manager()
        if not azure_manager:
            return {"message": f"Azure not configured"}
        # Run deletion in background to avoid blocking
        background_tasks.add_task(azure_manager.stop_and_delete_vm, vm_name)
        return {"message": f"VM {vm_name} deletion initiated"}
    except Exception as e:
        logger.error(f"Error deleting VM {vm_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete VM: {str(e)}")
