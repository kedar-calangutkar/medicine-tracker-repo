"""Platform for Medicine Tracker sensor."""
from __future__ import annotations

from datetime import datetime, time, timedelta
import logging
import pytz
from dateutil import rrule

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, CONF_NAME, CONF_ICON, CONF_DOSAGE,
    CONF_PATIENT, CONF_SCHEDULE_DAYS, CONF_SCHEDULE_TIME,
    CONF_TIME_MODE, CONF_TZ_SENSOR, MODE_LOCAL_TIME,
    CONF_MEDICINES
)

_LOGGER = logging.getLogger(__name__)

WEEKDAY_MAP = {
    "mon": rrule.MO, "tue": rrule.TU, "wed": rrule.WE,
    "thu": rrule.TH, "fri": rrule.FR, "sat": rrule.SA,
    "sun": rrule.SU
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform from UI Config Entry."""
    medicines_dict = entry.options.get(CONF_MEDICINES)
    if medicines_dict is None:
        medicines_dict = entry.data.get(CONF_MEDICINES, {})

    patient_id = entry.data.get(CONF_PATIENT)
    global_tz_sensor = entry.options.get(CONF_TZ_SENSOR, entry.data.get(CONF_TZ_SENSOR))

    sensors = []
    for med_id, med_data in medicines_dict.items():
        time_str = med_data.get(CONF_SCHEDULE_TIME)
        time_obj = time(8, 0)
        if time_str:
            try:
                time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
            except ValueError:
                pass 
        
        config = {
            CONF_NAME: med_data.get(CONF_NAME),
            CONF_ICON: med_data.get(CONF_ICON),
            CONF_DOSAGE: med_data.get(CONF_DOSAGE),
            CONF_PATIENT: patient_id, 
            CONF_SCHEDULE_DAYS: med_data.get(CONF_SCHEDULE_DAYS, []),
            CONF_SCHEDULE_TIME: time_obj,
            CONF_TIME_MODE: med_data.get(CONF_TIME_MODE),
            CONF_TZ_SENSOR: global_tz_sensor, 
        }
        
        unique_id = f"{entry.entry_id}_{med_id}"
        sensors.append(MedicineSensor(config, unique_id))
    
    async_add_entities(sensors)


class MedicineSensor(SensorEntity, RestoreEntity):
    """Representation of a Medicine Tracker Sensor."""

    def __init__(self, config, unique_id=None):
        """Initialize the sensor."""
        self._attr_unique_id = unique_id
        self._name = config[CONF_NAME]
        self._icon_default = config[CONF_ICON]
        self._icon = self._icon_default
        self._dosage = config.get(CONF_DOSAGE)
        self._patient_entity_id = config.get(CONF_PATIENT)
        
        self._schedule_time = config[CONF_SCHEDULE_TIME]
        self._schedule_days = config[CONF_SCHEDULE_DAYS]
        
        self._time_mode = config.get(CONF_TIME_MODE)
        self._tz_sensor = config.get(CONF_TZ_SENSOR)
        
        self._state = "Unknown"
        self._next_due = None
        self._patient_name = None
        self._history = [] 

    @property
    def name(self):
        return self._name

    @property
    def native_value(self):
        return self._state

    @property
    def icon(self):
        return self._icon
    
    @property
    def last_taken(self):
        """Return the last taken time from history."""
        if self._history:
            return self._history[-1]
        return None

    @property
    def extra_state_attributes(self):
        attributes = {
            "dosage": self._dosage,
            "patient_entity": self._patient_entity_id,
            "patient_name": self._patient_name,
            "schedule_time": self._schedule_time.strftime("%H:%M"),
            "schedule_days": self._schedule_days,
            "time_mode": self._time_mode,
        }
        
        if self.last_taken:
            attributes["last_taken"] = self.last_taken.isoformat()
            
        if self._next_due:
            attributes["next_due"] = self._next_due.isoformat()
        
        if self._history:
            attributes["history"] = [d.isoformat() for d in self._history]
            
        return attributes

    async def async_added_to_hass(self):
        """Restore state and resolve patient name."""
        await super().async_added_to_hass()
        
        if self._patient_entity_id:
            state = self.hass.states.get(self._patient_entity_id)
            if state:
                self._patient_name = state.attributes.get("friendly_name", state.name)
            else:
                self._patient_name = self._patient_entity_id

        last_state = await self.async_get_last_state()
        if last_state:
            # History Restoration
            if last_state.attributes.get("history"):
                try:
                    raw_history = last_state.attributes["history"]
                    self._history = [
                        dt_util.parse_datetime(d) 
                        for d in raw_history 
                        if dt_util.parse_datetime(d)
                    ]
                except Exception:
                    pass
            elif last_state.attributes.get("last_taken"):
                # Migration for old data
                try:
                    old_last = dt_util.parse_datetime(last_state.attributes["last_taken"])
                    if old_last:
                        self._history = [old_last]
                except Exception:
                    pass
        
        self._update_state()

    def _get_current_timezone(self):
        """Determine the effective timezone."""
        if self._time_mode == MODE_LOCAL_TIME and self._tz_sensor:
            tz_state = self.hass.states.get(self._tz_sensor)
            if tz_state and tz_state.state != "unknown":
                try:
                    return pytz.timezone(tz_state.state)
                except pytz.UnknownTimeZoneError:
                    pass
        return dt_util.DEFAULT_TIME_ZONE

    def _update_state(self):
        """Calculate next due date and set descriptive state."""
        try:
            tz = self._get_current_timezone()
            now_in_tz = dt_util.now(time_zone=tz)
            
            freq = rrule.DAILY
            byweekday = None
            
            if self._schedule_days:
                freq = rrule.WEEKLY
                parsed_days = []
                for d in self._schedule_days:
                    if d in WEEKDAY_MAP:
                        parsed_days.append(WEEKDAY_MAP[d])
                byweekday = parsed_days

            start_point = now_in_tz
            rule = rrule.rrule(freq, byweekday=byweekday, dtstart=start_point)
            
            today_due = now_in_tz.replace(
                hour=self._schedule_time.hour, 
                minute=self._schedule_time.minute, 
                second=0, microsecond=0
            )

            calculated_next = None

            # Check if taken today
            taken_today = False
            if self.last_taken:
                last_taken_local = self.last_taken.astimezone(tz)
                if last_taken_local.date() == now_in_tz.date():
                    taken_today = True

            if taken_today:
                # Taken today: Find next occurrence (likely tomorrow or later)
                next_occurrence = rule.after(now_in_tz)
                if next_occurrence:
                    calculated_next = next_occurrence.replace(
                        hour=self._schedule_time.hour, 
                        minute=self._schedule_time.minute,
                        second=0, microsecond=0
                    )
            else:
                # Not taken today: Check if we passed the time or it's coming up
                if now_in_tz > today_due:
                    # Time passed: It is Overdue
                    calculated_next = today_due
                else:
                    # Time is in future today
                    calculated_next = today_due
                
                # Verify day constraint (if today is not a scheduled day)
                if self._schedule_days:
                    weekday_str = now_in_tz.strftime("%a").lower()
                    if weekday_str not in self._schedule_days:
                        # Today invalid, find next
                        next_occurrence = rule.after(now_in_tz)
                        calculated_next = next_occurrence.replace(
                            hour=self._schedule_time.hour, 
                            minute=self._schedule_time.minute,
                            second=0, microsecond=0
                        )

            self._next_due = calculated_next
            
            if self._next_due:
                # -- IMPROVED STATE LOGIC --
                is_overdue = self._next_due < now_in_tz
                is_today = self._next_due.date() == now_in_tz.date()
                is_tomorrow = self._next_due.date() == (now_in_tz.date() + timedelta(days=1))

                if is_overdue:
                    self._state = "Overdue"
                    self._icon = "mdi:alert-circle"
                elif is_today:
                    # Format time as 12-hour
                    hour = self._next_due.strftime("%I").lstrip("0")
                    minute = self._next_due.strftime("%M")
                    ampm = self._next_due.strftime("%p")
                    
                    if minute == "00":
                        time_fmt = f"{hour} {ampm}"
                    else:
                        time_fmt = f"{hour}:{minute} {ampm}"

                    self._state = f"Due at {time_fmt}"
                    self._icon = "mdi:clock-outline"
                elif is_tomorrow:
                    self._state = "Due Tomorrow"
                    self._icon = "mdi:calendar-arrow-right"
                else:
                    self._state = f"Due {self._next_due.strftime('%A')}"
                    self._icon = "mdi:calendar"
            else:
                self._state = "Unknown"
                self._icon = "mdi:help-circle"

        except Exception as e:
            _LOGGER.error(f"Error updating medicine {self._name}: {e}")
            self._state = "Error"
            self._icon = "mdi:alert"

    async def mark_taken(self, custom_date=None):
        """Action: Mark the medicine as taken and log to history."""
        if custom_date:
            done_time = custom_date
            if done_time.tzinfo is None:
                done_time = done_time.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        else:
            done_time = dt_util.now()
            
        self._history.append(done_time)
        self._history.sort()
        self._history = self._history[-10:]
        self._update_state()
        self.async_write_ha_state()

    async def reset_history(self):
        """Action: Clear history."""
        self._history = []
        self._update_state()
        self.async_write_ha_state()