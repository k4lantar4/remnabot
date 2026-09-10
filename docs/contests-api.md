# Contests API (admin)

Admin REST API for contests: daily games and referral contests. Authentication matches the other methods — `X-API-Key` or Bearer.

## Daily games (`/contests/daily`)

- `GET /contests/daily/templates?enabled_only=false` — list game templates.
- `GET /contests/daily/templates/{id}` — get a template.
- `PATCH /contests/daily/templates/{id}` — update fields: `name`, `description`, `prize_type`, `prize_value`, `max_winners`, `attempts_per_user`, `times_per_day`, `schedule_times`, `cooldown_hours`, `payload` (dict), `is_enabled`.
- `POST /contests/daily/templates/{id}/start-round` — start a round manually. Body:
  ```json
  {
    "starts_at": "2025-12-15T09:00:00+03:00",
    "ends_at": "2025-12-15T13:00:00+03:00",
    "cooldown_hours": 4,
    "payload": {"secret_idx": 3},
    "force": true
  }
  ```
  If `force=true`, the active round for this template is finished before the new one is created.
- `GET /contests/daily/rounds?status_filter=active|finished|any&template_id&limit&offset` — list rounds.
- `GET /contests/daily/rounds/{id}` — get a round.
- `POST /contests/daily/rounds/{id}/finish` — finish a round.
- `GET /contests/daily/rounds/{id}/attempts?winners_only=false&limit&offset` — attempts (with user data).

## Referral contests (`/contests/referral`)

- `GET /contests/referral?contest_type&limit&offset` — list contests.
- `POST /contests/referral` — create a contest:
  ```json
  {
    "title": "December referrals",
    "contest_type": "referral_paid",
    "start_at": "2025-12-20T10:00:00+03:00",
    "end_at": "2025-12-27T10:00:00+03:00",
    "daily_summary_time": "12:00:00",
    "timezone": "Europe/Moscow",
    "prize_text": "🥇 5000 ₽, 🥈 3000 ₽",
    "is_active": true,
    "created_by": 1
  }
  ```
- `GET /contests/referral/{id}/detailed-stats` — detailed contest stats broken down by participant (`total_participants`, `total_invited`, `total_paid_amount`, `total_unpaid`, `participants`).
- `PATCH /contests/referral/{id}` — partial update (same fields plus `final_summary_sent`, `is_active`, `daily_summary_times` with multiple times comma-separated).
- `POST /contests/referral/{id}/toggle?is_active=true|false` — quickly enable or stop.
- `GET /contests/referral/{id}/events?limit&offset` — events (referrer/referral, type, amounts).
- `DELETE /contests/referral/{id}` — delete a finished contest.

## Dates and time zones

- `datetime` fields may include a TZ; the server converts them to UTC (tzinfo is stripped).
- If no TZ is specified, `settings.TIMEZONE` is used.

## OpenAPI tag

All methods are grouped under the `contests` tag in Swagger/Redoc after the web-api restart.
