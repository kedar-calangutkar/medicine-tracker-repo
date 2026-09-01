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

## Events
Medicine Tracker fires bus events you can trigger automations from, in addition to polling entity state/attributes.

### medicine_tracker_medicine_taken
Fires whenever a medicine is marked taken (via the `take_medicine` service), including backdated entries. Useful for clearing a notification you sent when the medicine became due.
```yaml
alias: "Clear Medicine Reminder Notification"
trigger:
  - platform: event
    event_type: medicine_tracker_medicine_taken
    event_data:
      entity_id: sensor.morning_pill
action:
  - service: notify.mobile_app_kedars_phone
    data:
      message: "clear_notification"
      data:
        tag: "morning_pill_reminder"
```
Event data: `entity_id`, `name`, `last_taken` (ISO timestamp), `next_due` (ISO timestamp or `null`).

### medicine_tracker_medicine_due
Fires the moment a medicine transitions into `Overdue` (not when it shows "Due at X" for later today, and not on every state check — only on that transition).
Event data: `entity_id`, `name`, `state`, `next_due` (ISO timestamp or `null`).
