Medicine Tracker
A smart home integration to track medication schedules for your family in Home Assistant.
Features
 * User Centric: Group medicines by person (Integration Entry).
 * Time Travel Ready:
   * Home Time: Locks schedule to your home server time (e.g., 8 PM Home Time).
   * Local Time: Adjusts schedule based on your phone's location (requires HA Companion App).
 * Smart Status:
   * "Due at 8 PM" (Friendly 12-hour format).
   * "Overdue" (Immediately upon passing scheduled time).
   * "Due Tomorrow".
 * History: Keeps a log of the last 10 times the medicine was taken.
Usage
 * Add Integration: Go to Settings > Devices & Services > Add Integration > Medicine Tracker.
 * Setup User: Select the Person (e.g., "Kedar") and their Timezone Sensor (e.g., sensor.iphone_current_time_zone).
 * Add Medicines: Click Configure on the new entry to Add, Edit, or Remove medicines.
 