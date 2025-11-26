"""Constants for the Medicine Tracker integration."""

DOMAIN = "medicine_tracker"

# Configuration Keys (Entry Level)
CONF_MEDICINES = "medicines" 
CONF_PATIENT = "patient"
CONF_TZ_SENSOR = "tz_sensor" # Global Timezone Sensor for the User

# Medicine Properties (Item Level)
CONF_MEDICINE_ID = "med_id"
CONF_NAME = "name"
CONF_ICON = "icon"
CONF_DOSAGE = "dosage"
CONF_SCHEDULE_DAYS = "days"
CONF_SCHEDULE_TIME = "time"
CONF_TIME_MODE = "time_mode"

# Modes
MODE_HOME_TIME = "home_time"
MODE_LOCAL_TIME = "local_time"