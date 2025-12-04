"""Tests for the Medicine Tracker component initialization."""
from unittest.mock import patch, AsyncMock
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.medicine_tracker.const import (
    DOMAIN, CONF_MEDICINES, CONF_PATIENT, CONF_NAME, CONF_ICON,
    CONF_DOSAGE, CONF_SCHEDULE_TIME, CONF_SCHEDULE_DAYS,
    CONF_TIME_MODE, MODE_HOME_TIME
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

async def test_setup_entry(hass: HomeAssistant):
    """Test setting up the integration from a config entry."""
    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Pill",
                CONF_SCHEDULE_TIME: "08:00:00",
                CONF_SCHEDULE_DAYS: [],
                CONF_TIME_MODE: MODE_HOME_TIME,
                CONF_ICON: "mdi:pill",
            }
        }
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.config.components

    # Check if sensor platform was forwarded by checking if entity exists
    state = hass.states.get("sensor.pill")
    assert state is not None

async def test_unload_entry(hass: HomeAssistant):
    """Test unloading the integration."""
    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {}
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)

async def test_services(hass: HomeAssistant):
    """Test service calls invoke entity methods."""
    # Setup entry and entity
    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Service Pill",
                CONF_SCHEDULE_TIME: "08:00:00",
                CONF_SCHEDULE_DAYS: [],
                CONF_TIME_MODE: MODE_HOME_TIME,
                CONF_ICON: "mdi:pill",
            }
        }
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.service_pill"

    # Mock the entity methods
    # We can't easily mock methods on the real entity instance created by the platform setup
    # unless we retrieve it from hass.data or similar.
    # But we can check the state changes which we already did in test_sensor.py.
    # Alternatively, we can patch the methods on the class before setup? No, that affects all tests.

    # Let's rely on side effects or state changes.

    # 1. Test take_medicine
    # Initial state should be valid (or unknown/overdue)
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        DOMAIN,
        "take_medicine",
        {"entity_id": entity_id},
        blocking=True
    )

    state = hass.states.get(entity_id)
    # Check history attribute grew
    assert len(state.attributes.get("history", [])) == 1

    # 2. Test reset_history
    await hass.services.async_call(
        DOMAIN,
        "reset_history",
        {"entity_id": entity_id},
        blocking=True
    )

    state = hass.states.get(entity_id)
    assert len(state.attributes.get("history", [])) == 0
