# Menu button statistics API usage

## Overview

The menu button click statistics system tracks which buttons users press most often.

## API endpoints

### 1. Log a button click

**POST** `/menu-layout/stats/log-click`

**Parameters:**

- `button_id` (str) — button ID
- `user_id` (int, optional) — user ID (`telegram_id`)
- `callback_data` (str, optional) — button `callback_data`
- `button_type` (str, optional) — button type: `builtin`, `callback`, `url`, `mini_app`
- `button_text` (str, optional) — button text at the time of the click

**Example:**

```python
await MenuLayoutService.log_button_click(
    db,
    button_id="menu_balance",
    user_id=123456789,
    callback_data="menu_balance",
    button_type="builtin",
    button_text="💰 Balance"
)
```

### 2. Get statistics for a specific button

**GET** `/menu-layout/stats/buttons/{button_id}?days=30`

**Returns:**

- `clicks_total` — total click count
- `clicks_today` — clicks today
- `clicks_week` — clicks this week
- `clicks_month` — clicks this month
- `unique_users` — unique users
- `last_click_at` — last click
- `clicks_by_day` — clicks by day

**Example:**

```python
stats = await MenuLayoutService.get_button_stats(db, "menu_balance", days=30)
# Returns:
# {
#     "button_id": "menu_balance",
#     "clicks_total": 150,
#     "clicks_today": 5,
#     "clicks_week": 25,
#     "clicks_month": 150,
#     "unique_users": 45,
#     "last_click_at": datetime(...)
# }
```

### 3. Get overall statistics for all buttons

**GET** `/menu-layout/stats?days=30`

**Returns:**

- `items` — statistics list for each button
- `total_clicks` — total click count
- `period_start` — period start
- `period_end` — period end

**Example:**

```python
all_stats = await MenuLayoutService.get_all_buttons_stats(db, days=30)
total = await MenuLayoutService.get_total_clicks(db, days=30)
```

## Automatic logging

**Button clicks are logged automatically.**

All button clicks are logged through `ButtonStatsMiddleware`. The middleware intercepts every `CallbackQuery` event and writes it to the database.

### How it works

1. On every button click the middleware automatically:
   - extracts `callback_data` (used as `button_id`)
   - gets `user_id` from the event
   - determines the button type (`builtin`, `callback`, `url`)
   - extracts button text from the keyboard (if available)
   - logs to the database asynchronously (does not block handling)

2. The middleware is enabled automatically when `MENU_LAYOUT_ENABLED=True`

3. Logging runs in the background and does not affect performance

### Manual logging (optional)

If you need to log clicks manually (for example for external integrations), use the API:

```python
# Via the service
await MenuLayoutService.log_button_click(
    db,
    button_id="custom_button",
    user_id=user_id,
    callback_data="custom_callback",
    button_type="callback",
    button_text="Custom button"
)

# Or via the API endpoint
POST /menu-layout/stats/log-click
{
    "button_id": "custom_button",
    "user_id": 123456789,
    "callback_data": "custom_callback",
    "button_type": "callback",
    "button_text": "Custom button"
}
```

### 4. Statistics by button type

**GET** `/menu-layout/stats/by-type?days=30`

**Returns:**

- Click statistics for each button type (`builtin`, `callback`, `url`, `mini_app`)
- Total clicks by type

**Example:**

```python
stats = await MenuLayoutService.get_stats_by_button_type(db, days=30)
# Returns:
# [
#     {"button_type": "builtin", "clicks_total": 500, "unique_users": 100},
#     {"button_type": "callback", "clicks_total": 200, "unique_users": 50},
#     ...
# ]
```

### 5. Statistics by hour of day

**GET** `/menu-layout/stats/by-hour?button_id=menu_balance&days=30`

**Parameters:**

- `button_id` (optional) — button ID to filter by
- `days` (default: 30) — period in days

**Returns:**

- Click distribution by hour of day (0–23)

**Example:**

```python
stats = await MenuLayoutService.get_clicks_by_hour(db, button_id="menu_balance", days=30)
# Returns:
# [
#     {"hour": 9, "count": 50},
#     {"hour": 10, "count": 75},
#     ...
# ]
```

### 6. Statistics by weekday

**GET** `/menu-layout/stats/by-weekday?button_id=menu_balance&days=30`

**Returns:**

- Click distribution by weekday (0 = Monday, 6 = Sunday)

**Example:**

```python
stats = await MenuLayoutService.get_clicks_by_weekday(db, button_id="menu_balance", days=30)
# Returns:
# [
#     {"weekday": 0, "weekday_name": "Monday", "count": 100},
#     {"weekday": 1, "weekday_name": "Tuesday", "count": 120},
#     ...
# ]
```

### 7. Top users by clicks

**GET** `/menu-layout/stats/top-users?button_id=menu_balance&limit=10&days=30`

**Parameters:**

- `button_id` (optional) — button ID to filter by
- `limit` (default: 10) — number of users
- `days` (default: 30) — period in days

**Returns:**

- Users with the highest click counts

**Example:**

```python
top_users = await MenuLayoutService.get_top_users(db, button_id="menu_balance", limit=10, days=30)
# Returns:
# [
#     {"user_id": 123456789, "clicks_count": 50, "last_click_at": datetime(...)},
#     ...
# ]
```

### 8. Period comparison

**GET** `/menu-layout/stats/compare?button_id=menu_balance&current_days=7&previous_days=7`

**Parameters:**

- `button_id` (optional) — button ID to filter by
- `current_days` (default: 7) — current comparison period
- `previous_days` (default: 7) — previous comparison period

**Returns:**

- Comparison of the current and previous periods
- Change in absolute numbers and percent
- Trend (`up` / `down` / `stable`)

**Example:**

```python
comparison = await MenuLayoutService.get_period_comparison(
    db, button_id="menu_balance", current_days=7, previous_days=7
)
# Returns:
# {
#     "current_period": {"clicks": 100, "days": 7, ...},
#     "previous_period": {"clicks": 80, "days": 7, ...},
#     "change": {"absolute": 20, "percent": 25.0, "trend": "up"}
# }
```

### 9. User click sequences

**GET** `/menu-layout/stats/users/{user_id}/sequences?limit=50`

**Parameters:**

- `user_id` (path) — user ID
- `limit` (default: 50) — maximum number of records

**Returns:**

- Chronological sequence of the user’s clicks

**Example:**

```python
sequences = await MenuLayoutService.get_user_click_sequences(db, user_id=123456789, limit=50)
# Returns:
# [
#     {"button_id": "menu_balance", "button_text": "💰 Balance", "clicked_at": datetime(...)},
#     {"button_id": "menu_subscription", "button_text": "📊 Subscription", "clicked_at": datetime(...)},
#     ...
# ]
```

## Important notes

1. **Automatic logging:** all button clicks are logged automatically through `ButtonStatsMiddleware`
2. **Authorization required:** statistics API endpoints require an auth token (`require_api_token`)
3. **button_id:** the button’s `callback_data` is used as the identifier
4. **Performance:** logging runs asynchronously in the background and does not block request handling
5. **Activation:** the middleware runs only if `MENU_LAYOUT_ENABLED=True` in settings
6. **Time zones:** all time metrics use the server’s local time
