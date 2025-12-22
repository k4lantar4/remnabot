"""
Tenant bots admin handlers - Modular structure.

This file now uses a modular structure where handlers are organized in separate modules:
- menu.py: Menu and list handlers
- create.py: Bot creation handlers
- detail.py: Bot detail view handler
- management.py: Bot activation/deactivation/delete handlers
- settings.py: Settings management handlers
- statistics.py: Statistics handlers
- feature_flags.py: Feature flags management handlers
- payments.py: Payment methods management handlers
- test.py: Test bot functionality handlers
- webhook.py: Webhook management handlers
- plans.py: Subscription plans handlers (placeholder)
- configuration.py: Configuration management handlers (placeholder)
- analytics.py: Analytics handlers (placeholder)

All handlers are registered via register.py module.
"""

from .register import register_handlers

__all__ = ['register_handlers']
