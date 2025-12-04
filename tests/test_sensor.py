"""Tests for the Medicine Tracker sensor."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest
from homeassistant.util import dt as dt_util
from homeassistant.const import STATE_UNKNOWN

from custom_components.medicine_tracker.const import (
    DOMAIN, CONF_MEDICINES, CONF_PATIENT, CONF_NAME, CONF_ICON,
    CONF_DOSAGE, CONF_SCHEDULE_TIME, CONF_SCHEDULE_DAYS,
    CONF_TIME_MODE, CONF_TZ_SENSOR, MODE_HOME_TIME, MODE_LOCAL_TIME
)

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from homeassistant.helpers.entity_component import async_update_entity

async def test_sensor_setup(hass):
    """Test setting up the sensor from config entry."""
    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Vitamin C",
                CONF_ICON: "mdi:pill",
                CONF_DOSAGE: "500mg",
                CONF_SCHEDULE_TIME: "08:00:00",
                CONF_SCHEDULE_DAYS: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                CONF_TIME_MODE: MODE_HOME_TIME,
            }
        }
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.vitamin_c")
    assert state is not None
    assert state.attributes["dosage"] == "500mg"
    assert state.attributes["schedule_time"] == "08:00"

async def test_sensor_state_calculations(hass):
    """Test state calculations (Due, Overdue, etc.)."""
    # Set time to 7:00 AM
    now = dt_util.now().replace(hour=7, minute=0, second=0, microsecond=0)

    with patch("homeassistant.util.dt.now", return_value=now):
        entry_data = {
            CONF_PATIENT: "person.test_user",
            CONF_MEDICINES: {
                "med1": {
                    CONF_NAME: "Morning Pill",
                    CONF_SCHEDULE_TIME: "08:00:00",
                    CONF_SCHEDULE_DAYS: [], # Every day
                    CONF_TIME_MODE: MODE_HOME_TIME,
                    CONF_ICON: "mdi:pill",
                }
            }
        }

        entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # 1. Check "Due at 08:00 AM"
        state = hass.states.get("sensor.morning_pill")
        assert "Due at 8 AM" in state.state
        assert state.attributes["next_due"] == now.replace(hour=8).isoformat()

    # 2. Check "Overdue"
    # Advance time to 8:30 AM
    now = now.replace(hour=8, minute=30)
    with patch("homeassistant.util.dt.now", return_value=now):
        # Update entity manually because patching dt.now doesn't trigger state update loop (if any)
        await async_update_entity(hass, "sensor.morning_pill")

        state = hass.states.get("sensor.morning_pill")
        assert state.state == "Overdue"

async def test_mark_taken(hass):
    """Test marking medicine as taken."""
    now = dt_util.now().replace(hour=9, minute=0, second=0, microsecond=0)
    with patch("homeassistant.util.dt.now", return_value=now):
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Initial: Overdue (since 9 > 8)
        state = hass.states.get("sensor.pill")
        assert state.state == "Overdue"

        # Call service to take medicine
        await hass.services.async_call(
            DOMAIN,
            "take_medicine",
            {"entity_id": "sensor.pill"},
            blocking=True
        )

        state = hass.states.get("sensor.pill")
        # Should be due tomorrow now
        assert state.state == "Due Tomorrow"
        assert len(state.attributes["history"]) == 1

async def test_schedule_days(hass):
    """Test specific schedule days."""
    # Monday
    now = dt_util.now().replace(hour=7, minute=0, second=0, microsecond=0)
    # Let's ensure 'now' is a Monday.
    # 2024-01-01 was a Monday.
    now = datetime(2024, 1, 1, 7, 0, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)

    with patch("homeassistant.util.dt.now", return_value=now):
        entry_data = {
            CONF_PATIENT: "person.test_user",
            CONF_MEDICINES: {
                "med1": {
                    CONF_NAME: "Weekly Pill",
                    CONF_SCHEDULE_TIME: "08:00:00",
                    CONF_SCHEDULE_DAYS: ["wed"], # Only Wednesday
                    CONF_TIME_MODE: MODE_HOME_TIME,
                    CONF_ICON: "mdi:pill",
                }
            }
        }

        entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.weekly_pill")
        # Today is Mon. Next Wed is 2 days away.
        # "Due Wednesday"
        assert state.state == "Due Wednesday"

        # Check next due attribute
        next_due = dt_util.parse_datetime(state.attributes["next_due"])
        assert next_due.weekday() == 2 # Wednesday
