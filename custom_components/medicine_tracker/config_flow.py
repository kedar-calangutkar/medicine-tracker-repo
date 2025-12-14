"""Config flow for Medicine Tracker integration."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
    TimeSelector,
    IconSelector,
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    DOMAIN, CONF_NAME, CONF_ICON, CONF_DOSAGE,
    CONF_PATIENT, CONF_SCHEDULE_DAYS, CONF_SCHEDULE_TIME,
    CONF_TIME_MODE, CONF_TZ_SENSOR,
    MODE_HOME_TIME, MODE_LOCAL_TIME,
    CONF_MEDICINES, CONF_MEDICINE_ID
)

_LOGGER = logging.getLogger(__name__)

TIME_MODE_OPTIONS = [
    SelectOptionDict(value=MODE_HOME_TIME, label="Home Time (Server Time)"),
    SelectOptionDict(value=MODE_LOCAL_TIME, label="Local Time (Follow Phone)"),
]

DAY_OPTIONS = [
    SelectOptionDict(value="mon", label="Monday"),
    SelectOptionDict(value="tue", label="Tuesday"),
    SelectOptionDict(value="wed", label="Wednesday"),
    SelectOptionDict(value="thu", label="Thursday"),
    SelectOptionDict(value="fri", label="Friday"),
    SelectOptionDict(value="sat", label="Saturday"),
    SelectOptionDict(value="sun", label="Sunday"),
]

def get_medicine_schema(defaults=None):
    """Build the schema for a single medicine (Simplified)."""
    if defaults is None:
        defaults = {}

    default_days = defaults.get(CONF_SCHEDULE_DAYS, [])
    default_time = defaults.get(CONF_SCHEDULE_TIME, "08:00:00")
    
    schema = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME)): str,
        vol.Optional(CONF_DOSAGE, default=defaults.get(CONF_DOSAGE, "")): str,
        vol.Optional(CONF_ICON, default=defaults.get(CONF_ICON, "mdi:pill")): IconSelector(),
        
        vol.Required(CONF_SCHEDULE_TIME, default=default_time): TimeSelector(),
        vol.Required(CONF_SCHEDULE_DAYS, default=default_days): SelectSelector(
            SelectSelectorConfig(options=DAY_OPTIONS, multiple=True)
        ),
        
        # We only ask for the mode now, not the sensor
        vol.Required(CONF_TIME_MODE, default=defaults.get(CONF_TIME_MODE, MODE_HOME_TIME)): SelectSelector(
            SelectSelectorConfig(options=TIME_MODE_OPTIONS, mode=SelectSelectorMode.DROPDOWN)
        ),
    }
    return vol.Schema(schema)


class MedicineTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Medicine Tracker."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MedicineTrackerOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Step 1: Setup User and Global Timezone Sensor."""
        errors = {}
        
        if user_input is not None:
            patient_id = user_input[CONF_PATIENT]
            
            await self.async_set_unique_id(patient_id)
            self._abort_if_unique_id_configured()

            state = self.hass.states.get(patient_id)
            name = state.attributes.get("friendly_name", state.name) if state else patient_id
            
            return self.async_create_entry(
                title=f"Medicines for {name}",
                data={
                    CONF_PATIENT: patient_id,
                    CONF_TZ_SENSOR: user_input.get(CONF_TZ_SENSOR), 
                    CONF_MEDICINES: {} 
                }
            )

        schema = vol.Schema({
            vol.Required(CONF_PATIENT): EntitySelector(
                EntitySelectorConfig(domain="person")
            ),
            # Global Timezone Sensor for this person
            vol.Optional(CONF_TZ_SENSOR): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            )
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class MedicineTrackerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # self.config_entry is now a read-only property in HA, so we do not set it manually.
        # We use the 'config_entry' argument passed to this function to initialize our data.
        self.medicines = {**config_entry.options.get(CONF_MEDICINES, config_entry.data.get(CONF_MEDICINES, {}))}
        self._editing_id = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Menu: Add/Edit/Remove/Settings."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_medicine", "edit_medicine", "remove_medicine", "global_settings"]
        )
    
    # --- SETTINGS ---
    async def async_step_global_settings(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Update global settings like Timezone Sensor."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_MEDICINES: self.medicines,
                    CONF_TZ_SENSOR: user_input.get(CONF_TZ_SENSOR)
                }
            )

        current_tz = self.config_entry.options.get(CONF_TZ_SENSOR, self.config_entry.data.get(CONF_TZ_SENSOR))
        
        schema = vol.Schema({
            vol.Optional(CONF_TZ_SENSOR, default=current_tz): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            )
        })
        
        return self.async_show_form(step_id="global_settings", data_schema=schema)

    # --- ADD ---
    async def async_step_add_medicine(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Form to add a new medicine."""
        if user_input is not None:
            new_id = str(uuid.uuid4())
            self.medicines[new_id] = user_input
            return await self._update_entry()

        return self.async_show_form(
            step_id="add_medicine", 
            data_schema=get_medicine_schema()
        )

    # --- EDIT ---
    async def async_step_edit_medicine(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if not self.medicines:
             return self.async_abort(reason="no_medicines")

        if user_input is not None:
            self._editing_id = user_input[CONF_MEDICINE_ID]
            return await self.async_step_edit_medicine_details()

        options = [
            SelectOptionDict(value=mid, label=data[CONF_NAME]) 
            for mid, data in self.medicines.items()
        ]
        schema = vol.Schema({
            vol.Required(CONF_MEDICINE_ID): SelectSelector(
                SelectSelectorConfig(options=options)
            )
        })
        return self.async_show_form(step_id="edit_medicine", data_schema=schema)

    async def async_step_edit_medicine_details(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self.medicines[self._editing_id] = user_input
            return await self._update_entry()

        existing_data = self.medicines[self._editing_id]
        return self.async_show_form(
            step_id="edit_medicine_details", 
            data_schema=get_medicine_schema(defaults=existing_data)
        )

    # --- REMOVE ---
    async def async_step_remove_medicine(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if not self.medicines:
             return self.async_abort(reason="no_medicines")
             
        if user_input is not None:
            mid = user_input[CONF_MEDICINE_ID]
            if mid in self.medicines:
                del self.medicines[mid]
            return await self._update_entry()

        options = [
            SelectOptionDict(value=mid, label=data[CONF_NAME]) 
            for mid, data in self.medicines.items()
        ]
        schema = vol.Schema({
            vol.Required(CONF_MEDICINE_ID): SelectSelector(
                SelectSelectorConfig(options=options)
            )
        })
        return self.async_show_form(step_id="remove_medicine", data_schema=schema)

    async def _update_entry(self):
        """Write changes back."""
        current_tz = self.config_entry.options.get(CONF_TZ_SENSOR, self.config_entry.data.get(CONF_TZ_SENSOR))
        
        return self.async_create_entry(
            title="",
            data={
                CONF_MEDICINES: self.medicines,
                CONF_TZ_SENSOR: current_tz
            }
        )

