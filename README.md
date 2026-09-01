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
 * Setup User: Enter a name for this person (e.g., "Kedar" - just a label, not a Home Assistant `person.*` entity), pick a `notify.*` service to target for reminders, and optionally a Timezone Sensor (e.g., sensor.iphone_current_time_zone) for Local Time mode.
 * Manage Medicines & Settings: Click Configure on the new entry to Add, Edit, or Remove medicines, or update Global Settings (name, notify target, timezone sensor) later.

## Services
Medicine Tracker exposes domain services, targeted at one or more medicine sensor entities.

### take_medicine
Marks a medicine as taken and logs it to history.
 * Arguments: `time_taken` (Optional): Override for when it was actually taken (defaults to now).

```yaml
action: medicine_tracker.take_medicine
target:
  entity_id: sensor.morning_pill
data:
  time_taken: "2024-01-01 08:15:00"
```

### reset_history
Clears the taken history.
```yaml
action: medicine_tracker.reset_history
target:
  entity_id: sensor.morning_pill
```

> Both services require a target `entity_id` and validate their input: calling one with no target, or with an unparseable `time_taken`, raises an error instead of silently doing the wrong thing (e.g. logging the dose as taken "now").

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
