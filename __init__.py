"""The Medicine Tracker integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.util import dt as dt_util
from .const import DOMAIN

SERVICE_TAKE = "take_medicine"
SERVICE_RESET = "reset_history"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Medicine Tracker services."""
    
    # 1. Take Medicine Service
    async def handle_take_medicine(call: ServiceCall):
        entity_ids = call.data.get("entity_id")
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        
        custom_date_str = call.data.get("time_taken")
        custom_date = None
        if custom_date_str:
            custom_date = dt_util.parse_datetime(custom_date_str)

        platforms = async_get_platforms(hass, DOMAIN)
        for platform in platforms:
            for entity in platform.entities.values():
                if entity.entity_id in entity_ids:
                    if hasattr(entity, "mark_taken"):
                        await entity.mark_taken(custom_date)

    # 2. Reset History Service
    async def handle_reset_history(call: ServiceCall):
        entity_ids = call.data.get("entity_id")
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
            
        platforms = async_get_platforms(hass, DOMAIN)
        for platform in platforms:
            for entity in platform.entities.values():
                if entity.entity_id in entity_ids:
                    if hasattr(entity, "reset_history"):
                        await entity.reset_history()

    hass.services.async_register(DOMAIN, SERVICE_TAKE, handle_take_medicine)
    hass.services.async_register(DOMAIN, SERVICE_RESET, handle_reset_history)
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medicine Tracker from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)