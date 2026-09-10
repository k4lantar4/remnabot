# Persistent cart for Remnawave Bedolaga Telegram Bot

## Overview

The persistent cart lets users continue subscription checkout after topping up their balance without losing already selected parameters (period, traffic, servers, devices, and so on).

## Architecture

### 1. Cart service (`UserCartService`)

Location: `app/services/user_cart_service.py`

Uses Redis to store cart data between user sessions.

#### Main methods:

- `save_user_cart(user_id, cart_data, ttl)` — saves the user’s cart
- `get_user_cart(user_id)` — returns the user’s cart data
- `delete_user_cart(user_id)` — deletes the user’s cart
- `has_user_cart(user_id)` — checks whether the user has a cart

### 2. Updated subscription handlers

Location: `app/handlers/subscription/purchase.py`

#### Main functions:

- `save_cart_and_redirect_to_topup` — saves the current cart to Redis when funds are insufficient and redirects to top-up
- `return_to_saved_cart` — restores subscription parameters from Redis and continues checkout
- `clear_saved_cart` — clears the saved cart

### 3. Updated keyboards

Location: `app/keyboards/inline.py`

#### Main changes:

- `get_insufficient_balance_keyboard` — added support for the `has_saved_cart` flag to show a return-to-checkout button
- `get_insufficient_balance_keyboard_with_cart` — updated to use the `has_saved_cart` flag
- `get_main_menu_keyboard` — added the `has_saved_cart` parameter to show a return-to-checkout button

### 4. Main menu integration

Location: `app/handlers/menu.py`

`show_main_menu` now checks for a saved cart and shows the corresponding button.

## Usage

### Saving the cart

When a user cannot complete a purchase because of insufficient funds, their parameters are automatically saved in Redis with a 1-hour TTL.

### Restoring the cart

After topping up, the user can return to subscription checkout by tapping **Return to subscription checkout** or via the main menu if they have a saved cart.

### Clearing the cart

The cart is cleared automatically after a successful subscription checkout or on the user’s request.

## Testing

Tests live in:

- `tests/test_user_cart_service.py` — unit tests for the cart service
- `tests/test_subscription_cart_integration.py` — integration tests

## Security

- Cart data is stored in Redis with a limited lifetime (TTL)
- The user identifier is used to isolate data
- The cart is cleared automatically after a successful purchase

## Scalability

- Redis lets the system scale across multiple bot instances
- TTL automatically cleans up old data
- Redis load is minimal because of the short storage lifetime
