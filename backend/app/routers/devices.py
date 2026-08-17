from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ..models import DeviceGroup, GroupStatusUpdate, QuickAction, NewDeviceGroup, NewDevice, Device
from ..services import device_service, firewall_service, logging_service
from .auth import get_current_user

router = APIRouter(prefix="/devices", tags=["devices"])

@router.get("/groups", response_model=List[DeviceGroup])
async def get_groups(current_user: str = Depends(get_current_user)):
    """Get all device groups"""
    groups = device_service.load_groups()
    
    # Check which groups are currently blocked
    blocked_macs = firewall_service.get_blocked_macs()
    
    for group in groups:
        if group.auto_detect:
            continue
        
        # Check if any device in the group is blocked
        group_blocked = any(
            device.mac.upper() in blocked_macs
            for device in group.devices
        )
        group.enabled = not group_blocked
    
    return groups

@router.post("/groups/{group_name}/toggle")
async def toggle_group(
    group_name: str,
    current_user: str = Depends(get_current_user)
):
    """Toggle a group's internet access"""
    group = device_service.get_group(group_name)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.protected:
        raise HTTPException(
            status_code=403,
            detail="Cannot block protected infrastructure group"
        )
    
    if group.auto_detect:
        raise HTTPException(
            status_code=400,
            detail="Cannot toggle auto-detect groups directly"
        )
    
    # Check current state
    blocked_macs = firewall_service.get_blocked_macs()
    is_blocked = any(device.mac.upper() in blocked_macs for device in group.devices)
    
    if is_blocked:
        # Unblock the group
        results = firewall_service.unblock_group(group.devices, group_name)
        action = "unblock"
        new_state = "enabled"
    else:
        # Block the group
        results = firewall_service.block_group(group.devices, group_name)
        action = "block"
        new_state = "disabled"
    
    # Log the action
    success = all(r.get('success', False) for r in results)
    logging_service.log_action(
        user=current_user,
        action=f"{action}_group",
        target=group_name,
        success=success,
        details=f"Group {new_state}"
    )
    
    return {
        "group": group_name,
        "action": action,
        "new_state": new_state,
        "results": results,
        "success": success
    }

@router.post("/groups/{group_name}/enable")
async def enable_group(
    group_name: str,
    current_user: str = Depends(get_current_user)
):
    """Enable internet access for a group"""
    group = device_service.get_group(group_name)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    results = firewall_service.unblock_group(group.devices, group_name)
    success = all(r.get('success', False) for r in results)
    
    logging_service.log_action(
        user=current_user,
        action="enable_group",
        target=group_name,
        success=success
    )
    
    return {
        "group": group_name,
        "action": "enable",
        "results": results,
        "success": success
    }

@router.post("/groups/{group_name}/disable")
async def disable_group(
    group_name: str,
    current_user: str = Depends(get_current_user)
):
    """Disable internet access for a group"""
    group = device_service.get_group(group_name)
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.protected:
        raise HTTPException(
            status_code=403,
            detail="Cannot block protected infrastructure group"
        )
    
    results = firewall_service.block_group(group.devices, group_name)
    success = all(r.get('success', False) for r in results)
    
    logging_service.log_action(
        user=current_user,
        action="disable_group",
        target=group_name,
        success=success
    )
    
    return {
        "group": group_name,
        "action": "disable",
        "results": results,
        "success": success
    }

@router.post("/quick-action")
async def quick_action(
    action: QuickAction,
    current_user: str = Depends(get_current_user)
):
    """Execute a quick action preset"""
    groups = device_service.load_groups()
    results = []
    
    if action.action == "enable_all":
        # Enable all non-protected groups
        for group in groups:
            if not group.protected and not group.auto_detect:
                group_results = firewall_service.unblock_group(group.devices, group.name)
                results.extend(group_results)
        
        logging_service.log_action(
            user=current_user,
            action="enable_all",
            target="all_groups",
            success=True
        )
    
    elif action.action == "only_essential":
        # Block everything except essential
        for group in groups:
            if group.name == "essential" or group.protected:
                continue
            if not group.auto_detect:
                group_results = firewall_service.block_group(group.devices, group.name)
                results.extend(group_results)
        
        # Ensure essential is unblocked
        essential = device_service.get_group("essential")
        if essential:
            essential_results = firewall_service.unblock_group(essential.devices, "essential")
            results.extend(essential_results)
        
        logging_service.log_action(
            user=current_user,
            action="only_essential",
            target="quick_action",
            success=True
        )
    
    elif action.action == "only_essential_security":
        # Block everything except essential and security
        for group in groups:
            if group.name in ["essential", "security"] or group.protected:
                continue
            if not group.auto_detect:
                group_results = firewall_service.block_group(group.devices, group.name)
                results.extend(group_results)
        
        # Ensure essential and security are unblocked
        for group_name in ["essential", "security"]:
            group = device_service.get_group(group_name)
            if group:
                group_results = firewall_service.unblock_group(group.devices, group_name)
                results.extend(group_results)
        
        logging_service.log_action(
            user=current_user,
            action="only_essential_security",
            target="quick_action",
            success=True
        )
    
    elif action.action == "block_kids":
        # This would require detecting unknown MACs on the network
        # For now, just log the action
        logging_service.log_action(
            user=current_user,
            action="block_kids",
            target="quick_action",
            success=True,
            details="Kids group blocking not yet implemented"
        )
    
    else:
        raise HTTPException(status_code=400, detail="Unknown quick action")
    
    return {
        "action": action.action,
        "results": results,
        "success": all(r.get('success', False) for r in results)
    }

@router.post("/groups", response_model=DeviceGroup, status_code=201)
async def create_group(
    payload: NewDeviceGroup,
    current_user: str = Depends(get_current_user)
):
    """Create a new device group"""
    try:
        new_group = device_service.add_group(
            name=payload.name,
            description=payload.description,
            auto_detect=payload.auto_detect
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logging_service.log_action(
        user=current_user, action="create_group", target=payload.name, success=True
    )
    return new_group


@router.delete("/groups/{group_name}")
async def delete_group(
    group_name: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a device group (must be empty and not protected)"""
    try:
        device_service.delete_group(group_name)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logging_service.log_action(
        user=current_user, action="delete_group", target=group_name, success=True
    )
    return {"group": group_name, "deleted": True}


@router.post("/groups/{group_name}/devices", response_model=Device, status_code=201)
async def add_device(
    group_name: str,
    device: NewDevice,
    current_user: str = Depends(get_current_user)
):
    """Add a device to an existing group"""
    try:
        new_device = device_service.add_device(group_name, Device(**device.model_dump()))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    all_devices = device_service.get_all_devices()
    firewall_service.sync_allowlist(all_devices)

    logging_service.log_action(
        user=current_user,
        action="add_device",
        target=f"{group_name}/{new_device.mac}",
        success=True,
        details=new_device.name
    )
    return new_device


@router.delete("/groups/{group_name}/devices/{mac}")
async def delete_device(
    group_name: str,
    mac: str,
    current_user: str = Depends(get_current_user)
):
    """Remove a device from a group"""
    try:
        device_service.delete_device(group_name, mac)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

    all_devices = device_service.get_all_devices()
    firewall_service.sync_allowlist(all_devices)

    logging_service.log_action(
        user=current_user,
        action="delete_device",
        target=f"{group_name}/{mac.upper()}",
        success=True
    )
    return {"group": group_name, "mac": mac.upper(), "deleted": True}


@router.post("/restore")
async def restore_backup(
    current_user: str = Depends(get_current_user)
):
    """Restore devices.yaml from the most recent backup"""
    try:
        restored_from = device_service.restore_latest_backup()
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))

    groups = device_service.reload_configuration()
    all_devices = device_service.get_all_devices()
    firewall_service.sync_allowlist(all_devices)

    logging_service.log_action(
        user=current_user, action="restore_backup", target=restored_from, success=True
    )
    return {"restored_from": restored_from, "groups_count": len(groups)}


@router.get("/firewall/rules")
async def get_firewall_rules(current_user: str = Depends(get_current_user)):
    """Get current firewall rules"""
    rules = firewall_service.get_current_rules()
    return {"rules": rules}

@router.post("/reload")
async def reload_config(current_user: str = Depends(get_current_user)):
    """Reload device configuration from disk"""
    groups = device_service.reload_configuration()

    all_devices = device_service.get_all_devices()
    firewall_service.sync_allowlist(all_devices)

    logging_service.log_action(
        user=current_user,
        action="reload_config",
        target="configuration",
        success=True
    )
    
    return {
        "message": "Configuration reloaded",
        "groups_count": len(groups)
    }
