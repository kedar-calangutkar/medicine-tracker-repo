"""Tests for the Medicine Tracker config flow."""
from unittest.mock import patch
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.medicine_tracker.const import (
    DOMAIN, CONF_MEDICINES, CONF_PATIENT, CONF_NAME, CONF_ICON,
    CONF_DOSAGE, CONF_SCHEDULE_TIME, CONF_SCHEDULE_DAYS,
    CONF_TIME_MODE, CONF_TZ_SENSOR, MODE_HOME_TIME, CONF_MEDICINE_ID
)

from pytest_homeassistant_custom_component.common import MockConfigEntry

async def test_user_flow(hass: HomeAssistant):
    """Test the full user configuration flow."""
    # 1. Start Flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # 2. Submit Form
    with patch("homeassistant.helpers.entity_registry.EntityRegistry.async_get"), \
         patch("homeassistant.core.StateMachine.get") as mock_get_state:

        # Mock state for person
        mock_get_state.return_value.name = "Test User"
        mock_get_state.return_value.attributes = {"friendly_name": "Test User Friendly"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PATIENT: "person.test_user",
                CONF_TZ_SENSOR: "sensor.phone_tz"
            }
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Medicines for Test User Friendly"
        assert result["data"][CONF_PATIENT] == "person.test_user"
        assert result["data"][CONF_TZ_SENSOR] == "sensor.phone_tz"

async def test_options_flow_add_medicine(hass: HomeAssistant):
    """Test adding a medicine via options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PATIENT: "person.test", CONF_MEDICINES: {}},
        entry_id="test_entry_id"
    )
    config_entry.add_to_hass(hass)

    # Start Options Flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    # Select "Add Medicine"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "add_medicine"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_medicine"

    # Fill Medicine Form
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "New Med",
            CONF_DOSAGE: "10mg",
            CONF_ICON: "mdi:pill",
            CONF_SCHEDULE_TIME: "09:00:00",
            CONF_SCHEDULE_DAYS: ["mon"],
            CONF_TIME_MODE: MODE_HOME_TIME
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Verify data stored in options
    medicines = result["data"][CONF_MEDICINES]
    assert len(medicines) == 1
    med_id = list(medicines.keys())[0]
    assert medicines[med_id][CONF_NAME] == "New Med"

async def test_options_flow_edit_medicine(hass: HomeAssistant):
    """Test editing a medicine."""
    med_id = "12345"
    med_data = {
        CONF_NAME: "Old Name",
        CONF_SCHEDULE_TIME: "08:00:00",
        CONF_SCHEDULE_DAYS: [],
        CONF_TIME_MODE: MODE_HOME_TIME,
        CONF_ICON: "mdi:pill"
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PATIENT: "person.test", CONF_MEDICINES: {med_id: med_data}},
        entry_id="test_entry_id"
    )
    config_entry.add_to_hass(hass)

    # Start Options Flow -> Edit
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_medicine"}
    )

    # Select Medicine to Edit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MEDICINE_ID: med_id}
    )

    # Edit Details
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "New Name",
            CONF_SCHEDULE_TIME: "08:00:00",
            CONF_SCHEDULE_DAYS: [],
            CONF_TIME_MODE: MODE_HOME_TIME,
            CONF_ICON: "mdi:pill"
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    medicines = result["data"][CONF_MEDICINES]
    assert medicines[med_id][CONF_NAME] == "New Name"

async def test_options_flow_remove_medicine(hass: HomeAssistant):
    """Test removing a medicine."""
    med_id = "12345"
    med_data = {
        CONF_NAME: "To Remove",
        CONF_SCHEDULE_TIME: "08:00:00",
        CONF_SCHEDULE_DAYS: [],
        CONF_TIME_MODE: MODE_HOME_TIME
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PATIENT: "person.test", CONF_MEDICINES: {med_id: med_data}},
        entry_id="test_entry_id"
    )
    config_entry.add_to_hass(hass)

    # Start Options Flow -> Remove
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "remove_medicine"}
    )

    # Select Medicine to Remove
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MEDICINE_ID: med_id}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    medicines = result["data"][CONF_MEDICINES]
    assert len(medicines) == 0
