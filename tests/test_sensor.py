"""Tests for the Medicine Tracker sensor."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest
import pytz
from homeassistant.core import State
from homeassistant.util import dt as dt_util
from homeassistant.const import STATE_UNKNOWN

from custom_components.medicine_tracker.const import (
    DOMAIN, CONF_MEDICINES, CONF_PATIENT, CONF_NAME, CONF_ICON,
    CONF_DOSAGE, CONF_SCHEDULE_TIME, CONF_SCHEDULE_DAYS,
    CONF_TIME_MODE, CONF_TZ_SENSOR, MODE_HOME_TIME, MODE_LOCAL_TIME
)

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry, async_fire_time_changed, async_capture_events,
    mock_restore_cache
)
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_platform import async_get_platforms


def _get_entity(hass, entity_id):
    """Look up a live MedicineSensor instance by entity_id."""
    for platform in async_get_platforms(hass, DOMAIN):
        for entity in platform.entities.values():
            if entity.entity_id == entity_id:
                return entity
    raise AssertionError(f"entity {entity_id} not found")


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

async def test_medicine_due_event_fires_only_on_overdue_transition(hass):
    """medicine_tracker_medicine_due fires when the state becomes Overdue,
    not when it merely shows "Due at X" for later today."""
    now = dt_util.now().replace(hour=7, minute=0, second=0, microsecond=0)

    with patch("homeassistant.util.dt.now", return_value=now):
        entry_data = {
            CONF_PATIENT: "person.test_user",
            CONF_MEDICINES: {
                "med1": {
                    CONF_NAME: "Due Event Pill",
                    CONF_SCHEDULE_TIME: "08:00:00",
                    CONF_SCHEDULE_DAYS: [],
                    CONF_TIME_MODE: MODE_HOME_TIME,
                    CONF_ICON: "mdi:pill",
                }
            }
        }

        entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
        entry.add_to_hass(hass)

        events = async_capture_events(hass, "medicine_tracker_medicine_due")

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Setup landed on "Due at 8 AM" (not yet due) - no event yet.
        state = hass.states.get("sensor.due_event_pill")
        assert "Due at 8 AM" in state.state
        assert len(events) == 0

    # Advance past the scheduled time -> Overdue. Event should fire once.
    now = now.replace(hour=8, minute=30)
    with patch("homeassistant.util.dt.now", return_value=now):
        await async_update_entity(hass, "sensor.due_event_pill")
        await hass.async_block_till_done()

        state = hass.states.get("sensor.due_event_pill")
        assert state.state == "Overdue"
        assert len(events) == 1
        assert events[0].data["entity_id"] == "sensor.due_event_pill"
        assert events[0].data["name"] == "Due Event Pill"
        assert events[0].data["state"] == "Overdue"

        # Further updates while still overdue must not re-fire the event.
        await async_update_entity(hass, "sensor.due_event_pill")
        await hass.async_block_till_done()
        assert len(events) == 1

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

async def test_mark_taken_fires_taken_event(hass):
    """take_medicine fires medicine_tracker_medicine_taken with the entity_id."""
    now = dt_util.now().replace(hour=9, minute=0, second=0, microsecond=0)
    with patch("homeassistant.util.dt.now", return_value=now):
        entry_data = {
            CONF_PATIENT: "person.test_user",
            CONF_MEDICINES: {
                "med1": {
                    CONF_NAME: "Taken Event Pill",
                    CONF_SCHEDULE_TIME: "08:00:00",
                    CONF_SCHEDULE_DAYS: [],
                    CONF_TIME_MODE: MODE_HOME_TIME,
                    CONF_ICON: "mdi:pill",
                }
            }
        }

        entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
        entry.add_to_hass(hass)

        events = async_capture_events(hass, "medicine_tracker_medicine_taken")

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            DOMAIN,
            "take_medicine",
            {"entity_id": "sensor.taken_event_pill"},
            blocking=True
        )
        await hass.async_block_till_done()

        assert len(events) == 1
        assert events[0].data["entity_id"] == "sensor.taken_event_pill"
        assert events[0].data["name"] == "Taken Event Pill"
        assert events[0].data["last_taken"] == now.isoformat()

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

async def test_invalid_schedule_time_falls_back_to_default(hass):
    """A malformed schedule_time string in stored config must not crash
    setup - it should fall back to the 08:00 default."""
    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Bad Time Config Pill",
                CONF_SCHEDULE_TIME: "not-a-time",
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

    state = hass.states.get("sensor.bad_time_config_pill")
    assert state is not None
    assert state.attributes["schedule_time"] == "08:00"

async def test_due_today_time_format_with_nonzero_minutes(hass):
    """"Due at" formatting includes the minutes when the scheduled time
    isn't exactly on the hour (e.g. 8:30 AM, not just "8 AM")."""
    now = dt_util.now().replace(hour=7, minute=0, second=0, microsecond=0)

    with patch("homeassistant.util.dt.now", return_value=now):
        entry_data = {
            CONF_PATIENT: "person.test_user",
            CONF_MEDICINES: {
                "med1": {
                    CONF_NAME: "Half Past Pill",
                    CONF_SCHEDULE_TIME: "08:30:00",
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

        state = hass.states.get("sensor.half_past_pill")
        assert "Due at 8:30 AM" in state.state

async def test_restore_history_current_format(hass):
    """History (a list of ISO completion timestamps) from a previous run
    is restored on startup so it survives a Home Assistant restart."""
    entity_id = "sensor.restore_pill"
    past1 = (dt_util.now() - timedelta(days=10)).isoformat()
    past2 = (dt_util.now() - timedelta(days=3)).isoformat()

    mock_restore_cache(hass, [
        State(entity_id, "Due Tomorrow", {"history": [past1, past2]})
    ])

    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Restore Pill",
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

    state = hass.states.get(entity_id)
    assert state is not None
    history = state.attributes["history"]
    assert history == [past1, past2]
    assert state.attributes["last_taken"] == past2

async def test_restore_legacy_last_taken_migrates_to_history(hass):
    """Entities restored from before the history list existed only had a
    single 'last_taken' attribute - it must be migrated into history
    rather than lost on upgrade."""
    entity_id = "sensor.legacy_pill"
    old_last = (dt_util.now() - timedelta(days=5)).isoformat()

    mock_restore_cache(hass, [
        State(entity_id, "Due Tomorrow", {"last_taken": old_last})
    ])

    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Legacy Pill",
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

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["last_taken"] == old_last
    assert state.attributes["history"] == [old_last]

async def test_restore_with_corrupted_history_does_not_crash_setup(hass):
    """A malformed 'history' attribute (e.g. from a corrupted restore
    cache) must not crash setup - the entity should just start empty."""
    entity_id = "sensor.corrupted_history_pill"

    mock_restore_cache(hass, [
        State(entity_id, "Due Tomorrow", {"history": [123, 456]})
    ])

    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Corrupted History Pill",
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

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "Error"
    assert "history" not in state.attributes

async def test_restore_with_corrupted_last_taken_does_not_crash_setup(hass):
    """A malformed legacy 'last_taken' attribute must not crash setup -
    the entity should just start with no history."""
    entity_id = "sensor.corrupted_last_taken_pill"

    mock_restore_cache(hass, [
        State(entity_id, "Due Tomorrow", {"last_taken": 12345})
    ])

    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Corrupted Last Taken Pill",
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

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "Error"
    assert "history" not in state.attributes

async def test_local_time_mode_uses_tz_sensor_state(hass):
    """MODE_LOCAL_TIME resolves the effective timezone from the configured
    tz_sensor's state instead of always using the HA server's timezone."""
    hass.states.async_set("sensor.phone_tz", "America/New_York")

    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_TZ_SENSOR: "sensor.phone_tz",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Local Time Pill",
                CONF_SCHEDULE_TIME: "08:00:00",
                CONF_SCHEDULE_DAYS: [],
                CONF_TIME_MODE: MODE_LOCAL_TIME,
                CONF_ICON: "mdi:pill",
            }
        }
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = _get_entity(hass, "sensor.local_time_pill")
    assert entity._get_current_timezone() == pytz.timezone("America/New_York")

async def test_local_time_mode_falls_back_to_default_timezone(hass):
    """Falls back to the HA default timezone when the tz_sensor doesn't
    exist yet, is unknown, or holds a value pytz can't resolve - rather
    than crashing the update."""
    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_TZ_SENSOR: "sensor.phone_tz",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Fallback Tz Pill",
                CONF_SCHEDULE_TIME: "08:00:00",
                CONF_SCHEDULE_DAYS: [],
                CONF_TIME_MODE: MODE_LOCAL_TIME,
                CONF_ICON: "mdi:pill",
            }
        }
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = _get_entity(hass, "sensor.fallback_tz_pill")

    # tz_sensor entity doesn't exist at all yet.
    assert entity._get_current_timezone() == dt_util.DEFAULT_TIME_ZONE

    # tz_sensor exists but hasn't reported a value yet.
    hass.states.async_set("sensor.phone_tz", "unknown")
    assert entity._get_current_timezone() == dt_util.DEFAULT_TIME_ZONE

    # tz_sensor reports something pytz can't parse as a timezone.
    hass.states.async_set("sensor.phone_tz", "Not/ARealZone")
    assert entity._get_current_timezone() == dt_util.DEFAULT_TIME_ZONE

async def test_update_state_sets_error_on_exception(hass):
    """An unexpected exception while calculating state must be caught and
    surfaced as an Error state/icon rather than crashing the update."""
    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Error Pill",
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

    entity = _get_entity(hass, "sensor.error_pill")
    entity._schedule_time = None  # corrupt internal state to force a crash
    entity._update_state()

    assert entity.native_value == "Error"
    assert entity.icon == "mdi:alert"

async def test_take_medicine_with_naive_time_taken_applies_default_timezone(hass):
    """A naive (no offset) time_taken value is normalized with the HA
    default timezone rather than being rejected or misinterpreted."""
    entry_data = {
        CONF_PATIENT: "person.test_user",
        CONF_MEDICINES: {
            "med1": {
                CONF_NAME: "Explicit Time Pill",
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

    entity_id = "sensor.explicit_time_pill"
    naive_time_str = "2024-01-01T09:00:00"

    await hass.services.async_call(
        DOMAIN, "take_medicine",
        {"entity_id": entity_id, "time_taken": naive_time_str},
        blocking=True,
    )

    expected = dt_util.parse_datetime(naive_time_str).replace(
        tzinfo=dt_util.DEFAULT_TIME_ZONE
    )
    state = hass.states.get(entity_id)
    assert state.attributes["last_taken"] == expected.isoformat()
