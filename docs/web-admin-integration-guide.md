# Guide to integrating WebSocket and webhooks into the web admin

## Contents

1. [Overview](#overview)
2. [Setting up the WebSocket connection](#setting-up-the-websocket-connection)
3. [Integrating WebSocket into the dashboard](#integrating-websocket-into-the-dashboard)
4. [Managing webhooks through the API](#managing-webhooks-through-the-api)
5. [UI components for webhooks](#ui-components-for-webhooks)
6. [Error handling](#error-handling)
7. [Testing](#testing)

---

## Overview

The web admin can use two mechanisms to receive updates:

1. **WebSocket** — real-time UI updates (new users, payments, tickets)
2. **Webhooks** — configuring external integrations (sending events to external servers)

---

## Setting up the WebSocket connection

### Step 1: Create a WebSocket manager

Create a utility to manage the WebSocket connection:

```typescript
// utils/websocket.ts
class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private listeners: Map<string, Set<Function>> = new Map();
  private apiToken: string;

  constructor(apiToken: string) {
    this.apiToken = apiToken;
  }

  connect(url: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    const wsUrl = `${url}?token=${this.apiToken}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.emit('connected', {});
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.emit('error', { error });
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.emit('disconnected', {});
      this.attemptReconnect(url);
    };

    // Keepalive ping every 30 seconds
    setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  private handleMessage(data: any): void {
    if (data.type === 'pong') {
      return; // Ignore pong
    }

    if (data.type === 'connection') {
      this.emit('connection', data);
      return;
    }

    // Emit an event by type
    this.emit(data.type, data.payload);
  }

  private attemptReconnect(url: string): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    setTimeout(() => {
      console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`);
      this.connect(url);
    }, delay);
  }

  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: Function): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }

  private emit(event: string, data: any): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event listener for ${event}:`, error);
        }
      });
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export default WebSocketManager;
```

### Step 2: Initialize in the application

```typescript
// App.tsx or main.tsx
import { useEffect, useState } from 'react';
import WebSocketManager from './utils/websocket';
import { getApiToken } from './utils/auth';

function App() {
  const [wsManager, setWsManager] = useState<WebSocketManager | null>(null);

  useEffect(() => {
    const token = getApiToken();
    if (!token) {
      console.warn('No API token found, WebSocket will not connect');
      return;
    }

    const manager = new WebSocketManager(token);
    const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8080/ws';

    manager.connect(wsUrl);
    setWsManager(manager);

    // Event handling
    manager.on('user.created', (payload) => {
      console.log('New user created:', payload);
      // Refresh the user list
      // Show a notification
    });

    manager.on('payment.completed', (payload) => {
      console.log('Payment completed:', payload);
      // Refresh statistics
      // Refresh the user balance
    });

    manager.on('ticket.created', (payload) => {
      console.log('New ticket created:', payload);
      // Refresh the ticket list
      // Show a notification
    });

    manager.on('ticket.status_changed', (payload) => {
      console.log('Ticket status changed:', payload);
      // Update the ticket status in the list
    });

    manager.on('ticket.message_added', (payload) => {
      console.log('New message in ticket:', payload);
      // Refresh the message list in the ticket
      // Show a notification about the new message
    });

    return () => {
      manager.disconnect();
    };
  }, []);

  return (
    // Your application component
  );
}
```

---

## Integrating WebSocket into the dashboard

### Step 1: Create a React hook for WebSocket

```typescript
// hooks/useWebSocket.ts
import { useEffect, useState, useCallback } from 'react';
import { useWebSocketContext } from '../contexts/WebSocketContext';

export function useWebSocketEvent<T = any>(eventType: string) {
  const { wsManager } = useWebSocketContext();
  const [data, setData] = useState<T | null>(null);

  useEffect(() => {
    if (!wsManager) return;

    const handler = (payload: T) => {
      setData(payload);
    };

    wsManager.on(eventType, handler);

    return () => {
      wsManager.off(eventType, handler);
    };
  }, [wsManager, eventType]);

  return data;
}

// Usage in a component
function Dashboard() {
  const newUser = useWebSocketEvent('user.created');
  const newPayment = useWebSocketEvent('payment.completed');
  const newTicket = useWebSocketEvent('ticket.created');

  useEffect(() => {
    if (newUser) {
      // Update the user counter
      // Show a toast notification
    }
  }, [newUser]);

  return (
    // Your dashboard
  );
}
```

### Step 2: Real-time counter updates

```typescript
// components/DashboardStats.tsx
import { useState, useEffect } from 'react';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { fetchStats } from '../api/stats';

function DashboardStats() {
  const { wsManager } = useWebSocketContext();
  const [stats, setStats] = useState({
    totalUsers: 0,
    activeSubscriptions: 0,
    openTickets: 0,
    todayRevenue: 0,
  });

  // Load initial data
  useEffect(() => {
    loadStats();
  }, []);

  // Subscribe to events for updates
  useEffect(() => {
    if (!wsManager) return;

    const updateOnNewUser = () => {
      setStats(prev => ({ ...prev, totalUsers: prev.totalUsers + 1 }));
    };

    const updateOnPayment = (payload: any) => {
      setStats(prev => ({
        ...prev,
        todayRevenue: prev.todayRevenue + (payload.amount_rubles || 0),
      }));
    };

    const updateOnTicket = () => {
      setStats(prev => ({ ...prev, openTickets: prev.openTickets + 1 }));
    };

    wsManager.on('user.created', updateOnNewUser);
    wsManager.on('payment.completed', updateOnPayment);
    wsManager.on('ticket.created', updateOnTicket);
    wsManager.on('ticket.message_added', updateOnTicketMessage);

    return () => {
      wsManager.off('user.created', updateOnNewUser);
      wsManager.off('payment.completed', updateOnPayment);
      wsManager.off('ticket.created', updateOnTicket);
      wsManager.off('ticket.message_added', updateOnTicketMessage);
    };
  }, [wsManager]);

  const loadStats = async () => {
    try {
      const data = await fetchStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  return (
    <div className="stats-grid">
      <StatCard title="Total users" value={stats.totalUsers} />
      <StatCard title="Active subscriptions" value={stats.activeSubscriptions} />
      <StatCard title="Open tickets" value={stats.openTickets} />
      <StatCard title="Revenue today" value={`${stats.todayRevenue} ₽`} />
    </div>
  );
}
```

### Step 3: Notifications for new events

```typescript
// components/NotificationCenter.tsx
import { useState, useEffect } from 'react';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { toast } from 'react-toastify';

interface Notification {
  id: string;
  type: string;
  message: string;
  timestamp: Date;
}

function NotificationCenter() {
  const { wsManager } = useWebSocketContext();
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    if (!wsManager) return;

    const handleNewUser = (payload: any) => {
      const notification: Notification = {
        id: `user-${payload.user_id}`,
        type: 'user.created',
        message: `New user: @${payload.username || payload.telegram_id}`,
        timestamp: new Date(),
      };
      addNotification(notification);
      toast.info(notification.message);
    };

    const handleNewPayment = (payload: any) => {
      const notification: Notification = {
        id: `payment-${payload.transaction_id}`,
        type: 'payment.completed',
        message: `Balance top-up: ${payload.amount_rubles} ₽`,
        timestamp: new Date(),
      };
      addNotification(notification);
      toast.success(notification.message);
    };

    const handleNewTicket = (payload: any) => {
      const notification: Notification = {
        id: `ticket-${payload.ticket_id}`,
        type: 'ticket.created',
        message: `New ticket: ${payload.title}`,
        timestamp: new Date(),
      };
      addNotification(notification);
      toast.warning(notification.message, {
        onClick: () => {
          // Navigate to the ticket
          window.location.href = `/tickets/${payload.ticket_id}`;
        },
      });
    };

    const handleNewMessage = (payload: any) => {
      const notification: Notification = {
        id: `ticket-message-${payload.message_id}`,
        type: 'ticket.message_added',
        message: payload.is_from_admin
          ? `New reply in ticket #${payload.ticket_id}`
          : `New user message in ticket #${payload.ticket_id}`,
        timestamp: new Date(),
      };
      addNotification(notification);
      toast.info(notification.message, {
        onClick: () => {
          // Navigate to the ticket
          window.location.href = `/tickets/${payload.ticket_id}`;
        },
      });
    };

    wsManager.on('user.created', handleNewUser);
    wsManager.on('payment.completed', handleNewPayment);
    wsManager.on('ticket.created', handleNewTicket);
    wsManager.on('ticket.message_added', handleNewMessage);

    return () => {
      wsManager.off('user.created', handleNewUser);
      wsManager.off('payment.completed', handleNewPayment);
      wsManager.off('ticket.created', handleNewTicket);
      wsManager.off('ticket.message_added', handleNewMessage);
    };
  }, [wsManager]);

  const addNotification = (notification: Notification) => {
    setNotifications(prev => [notification, ...prev].slice(0, 50)); // Keep the last 50
  };

  return (
    <div className="notification-center">
      {notifications.map(notif => (
        <NotificationItem key={notif.id} notification={notif} />
      ))}
    </div>
  );
}
```

---

## Managing webhooks through the API

### Step 1: API client for webhooks

```typescript
// api/webhooks.ts
import { apiClient } from './client';

export interface Webhook {
  id: number;
  name: string;
  url: string;
  event_type: string;
  is_active: boolean;
  description?: string;
  created_at: string;
  updated_at: string;
  last_triggered_at?: string;
  failure_count: number;
  success_count: number;
}

export interface WebhookCreateRequest {
  name: string;
  url: string;
  event_type: string;
  secret?: string;
  description?: string;
}

export interface WebhookUpdateRequest {
  name?: string;
  url?: string;
  secret?: string;
  description?: string;
  is_active?: boolean;
}

export const webhooksApi = {
  // Webhook list
  list: async (params?: {
    event_type?: string;
    is_active?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<{ items: Webhook[]; total: number }> => {
    const response = await apiClient.get('/webhooks', { params });
    return response.data;
  },

  // Get a webhook
  get: async (id: number): Promise<Webhook> => {
    const response = await apiClient.get(`/webhooks/${id}`);
    return response.data;
  },

  // Create a webhook
  create: async (data: WebhookCreateRequest): Promise<Webhook> => {
    const response = await apiClient.post('/webhooks', data);
    return response.data;
  },

  // Update a webhook
  update: async (id: number, data: WebhookUpdateRequest): Promise<Webhook> => {
    const response = await apiClient.patch(`/webhooks/${id}`, data);
    return response.data;
  },

  // Delete a webhook
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/webhooks/${id}`);
  },

  // Statistics
  getStats: async (): Promise<{
    total_webhooks: number;
    active_webhooks: number;
    total_deliveries: number;
    successful_deliveries: number;
    failed_deliveries: number;
    success_rate: number;
  }> => {
    const response = await apiClient.get('/webhooks/stats');
    return response.data;
  },

  // Delivery history
  getDeliveries: async (
    webhookId: number,
    params?: { status?: string; limit?: number; offset?: number }
  ): Promise<{ items: any[]; total: number }> => {
    const response = await apiClient.get(`/webhooks/${webhookId}/deliveries`, { params });
    return response.data;
  },
};
```

### Step 2: List of available event types

```typescript
// constants/webhookEvents.ts
export const WEBHOOK_EVENT_TYPES = [
  {
    value: 'user.created',
    label: 'User created',
    description: 'Sent when a new user registers',
  },
  {
    value: 'payment.completed',
    label: 'Payment completed',
    description: 'Sent when a balance top-up succeeds',
  },
  {
    value: 'transaction.created',
    label: 'Transaction created',
    description: 'Sent when any transaction is created',
  },
  {
    value: 'ticket.created',
    label: 'Ticket created',
    description: 'Sent when a new support ticket is created',
  },
  {
    value: 'ticket.status_changed',
    label: 'Ticket status changed',
    description: 'Sent when a ticket status changes',
  },
  {
    value: 'ticket.message_added',
    label: 'New ticket message',
    description: 'Sent when a new message is added to a ticket (from the user or an admin)',
  },
] as const;

export type WebhookEventType = typeof WEBHOOK_EVENT_TYPES[number]['value'];
```

---

## UI components for webhooks

### Step 1: Webhook create/edit form

```typescript
// components/WebhookForm.tsx
import { useState } from 'react';
import { webhooksApi, WebhookCreateRequest, WebhookUpdateRequest } from '../api/webhooks';
import { WEBHOOK_EVENT_TYPES } from '../constants/webhookEvents';

interface WebhookFormProps {
  webhook?: Webhook;
  onSuccess: () => void;
  onCancel: () => void;
}

function WebhookForm({ webhook, onSuccess, onCancel }: WebhookFormProps) {
  const [formData, setFormData] = useState({
    name: webhook?.name || '',
    url: webhook?.url || '',
    event_type: webhook?.event_type || '',
    secret: '',
    description: webhook?.description || '',
    is_active: webhook?.is_active ?? true,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (webhook) {
        await webhooksApi.update(webhook.id, formData);
      } else {
        await webhooksApi.create(formData);
      }
      onSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error saving webhook');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="webhook-form">
      <div className="form-group">
        <label>Name *</label>
        <input
          type="text"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          required
        />
      </div>

      <div className="form-group">
        <label>URL *</label>
        <input
          type="url"
          value={formData.url}
          onChange={(e) => setFormData({ ...formData, url: e.target.value })}
          required
          placeholder="https://example.com/webhook"
        />
      </div>

      <div className="form-group">
        <label>Event type *</label>
        <select
          value={formData.event_type}
          onChange={(e) => setFormData({ ...formData, event_type: e.target.value })}
          required
          disabled={!!webhook} // Event type cannot be changed for an existing webhook
        >
          <option value="">Select an event type</option>
          {WEBHOOK_EVENT_TYPES.map((event) => (
            <option key={event.value} value={event.value}>
              {event.label}
            </option>
          ))}
        </select>
        {formData.event_type && (
          <small>
            {WEBHOOK_EVENT_TYPES.find((e) => e.value === formData.event_type)?.description}
          </small>
        )}
      </div>

      <div className="form-group">
        <label>Secret (optional)</label>
        <input
          type="password"
          value={formData.secret}
          onChange={(e) => setFormData({ ...formData, secret: e.target.value })}
          placeholder="For payload signing"
        />
        <small>If set, the payload is signed with HMAC-SHA256</small>
      </div>

      <div className="form-group">
        <label>Description</label>
        <textarea
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          rows={3}
        />
      </div>

      {webhook && (
        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
            />
            Active
          </label>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      <div className="form-actions">
        <button type="button" onClick={onCancel} disabled={loading}>
          Cancel
        </button>
        <button type="submit" disabled={loading}>
          {loading ? 'Saving...' : webhook ? 'Update' : 'Create'}
        </button>
      </div>
    </form>
  );
}
```

### Step 2: Webhook list

```typescript
// components/WebhooksList.tsx
import { useState, useEffect } from 'react';
import { webhooksApi, Webhook } from '../api/webhooks';
import WebhookForm from './WebhookForm';
import WebhookDeliveries from './WebhookDeliveries';

function WebhooksList() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedWebhook, setSelectedWebhook] = useState<Webhook | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<Webhook | null>(null);

  useEffect(() => {
    loadWebhooks();
  }, []);

  const loadWebhooks = async () => {
    try {
      setLoading(true);
      const data = await webhooksApi.list();
      setWebhooks(data.items);
    } catch (error) {
      console.error('Failed to load webhooks:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this webhook?')) return;

    try {
      await webhooksApi.delete(id);
      loadWebhooks();
    } catch (error) {
      console.error('Failed to delete webhook:', error);
    }
  };

  const handleToggleActive = async (webhook: Webhook) => {
    try {
      await webhooksApi.update(webhook.id, { is_active: !webhook.is_active });
      loadWebhooks();
    } catch (error) {
      console.error('Failed to update webhook:', error);
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="webhooks-page">
      <div className="page-header">
        <h1>Webhooks</h1>
        <button onClick={() => setShowForm(true)}>Create webhook</button>
      </div>

      {showForm && (
        <div className="modal">
          <div className="modal-content">
            <h2>{editingWebhook ? 'Edit' : 'Create'} Webhook</h2>
            <WebhookForm
              webhook={editingWebhook || undefined}
              onSuccess={() => {
                setShowForm(false);
                setEditingWebhook(null);
                loadWebhooks();
              }}
              onCancel={() => {
                setShowForm(false);
                setEditingWebhook(null);
              }}
            />
          </div>
        </div>
      )}

      <table className="webhooks-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>URL</th>
            <th>Event type</th>
            <th>Status</th>
            <th>Succeeded</th>
            <th>Errors</th>
            <th>Last call</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {webhooks.map((webhook) => (
            <tr key={webhook.id}>
              <td>{webhook.name}</td>
              <td>
                <code>{webhook.url}</code>
              </td>
              <td>{webhook.event_type}</td>
              <td>
                <span className={`status ${webhook.is_active ? 'active' : 'inactive'}`}>
                  {webhook.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td>{webhook.success_count}</td>
              <td className={webhook.failure_count > 0 ? 'error' : ''}>
                {webhook.failure_count}
              </td>
              <td>
                {webhook.last_triggered_at
                  ? new Date(webhook.last_triggered_at).toLocaleString()
                  : 'Never'}
              </td>
              <td>
                <button onClick={() => handleToggleActive(webhook)}>
                  {webhook.is_active ? 'Deactivate' : 'Activate'}
                </button>
                <button onClick={() => {
                  setEditingWebhook(webhook);
                  setShowForm(true);
                }}>
                  Edit
                </button>
                <button onClick={() => setSelectedWebhook(webhook)}>
                  History
                </button>
                <button onClick={() => handleDelete(webhook.id)} className="danger">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedWebhook && (
        <WebhookDeliveries
          webhookId={selectedWebhook.id}
          onClose={() => setSelectedWebhook(null)}
        />
      )}
    </div>
  );
}
```

### Step 3: Webhook delivery history

```typescript
// components/WebhookDeliveries.tsx
import { useState, useEffect } from 'react';
import { webhooksApi } from '../api/webhooks';

interface WebhookDeliveriesProps {
  webhookId: number;
  onClose: () => void;
}

function WebhookDeliveries({ webhookId, onClose }: WebhookDeliveriesProps) {
  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');

  useEffect(() => {
    loadDeliveries();
  }, [webhookId, statusFilter]);

  const loadDeliveries = async () => {
    try {
      setLoading(true);
      const data = await webhooksApi.getDeliveries(webhookId, {
        status: statusFilter || undefined,
        limit: 50,
      });
      setDeliveries(data.items);
    } catch (error) {
      console.error('Failed to load deliveries:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal">
      <div className="modal-content large">
        <div className="modal-header">
          <h2>Delivery history</h2>
          <button onClick={onClose}>×</button>
        </div>

        <div className="filters">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            <option value="success">Succeeded</option>
            <option value="failed">Error</option>
            <option value="pending">Pending</option>
          </select>
        </div>

        {loading ? (
          <div>Loading...</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Status</th>
                <th>HTTP code</th>
                <th>Error</th>
                <th>Attempt</th>
              </tr>
            </thead>
            <tbody>
              {deliveries.map((delivery) => (
                <tr key={delivery.id}>
                  <td>{new Date(delivery.created_at).toLocaleString()}</td>
                  <td>{delivery.event_type}</td>
                  <td>
                    <span className={`status ${delivery.status}`}>
                      {delivery.status}
                    </span>
                  </td>
                  <td>{delivery.response_status || '-'}</td>
                  <td>
                    {delivery.error_message ? (
                      <span className="error" title={delivery.error_message}>
                        {delivery.error_message.substring(0, 50)}...
                      </span>
                    ) : (
                      '-'
                    )}
                  </td>
                  <td>{delivery.attempt_number}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
```

---

## Error handling

### WebSocket error handling

```typescript
// utils/websocket.ts (addition)
class WebSocketManager {
  // ... existing code ...

  private handleError(error: Error): void {
    console.error('WebSocket error:', error);

    // Notify the user
    this.emit('error', {
      message: 'Server connection error',
      error: error.message,
    });

    // Automatic reconnect
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.attemptReconnect(this.wsUrl);
    }
  }

  // Connection status
  getConnectionStatus(): 'connected' | 'disconnected' | 'connecting' {
    if (!this.ws) return 'disconnected';
    if (this.ws.readyState === WebSocket.OPEN) return 'connected';
    if (this.ws.readyState === WebSocket.CONNECTING) return 'connecting';
    return 'disconnected';
  }
}
```

### Connection status indicator

```typescript
// components/ConnectionStatus.tsx
import { useWebSocketContext } from '../contexts/WebSocketContext';

function ConnectionStatus() {
  const { wsManager } = useWebSocketContext();
  const [status, setStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');

  useEffect(() => {
    if (!wsManager) return;

    const updateStatus = () => {
      setStatus(wsManager.getConnectionStatus());
    };

    wsManager.on('connected', updateStatus);
    wsManager.on('disconnected', updateStatus);

    const interval = setInterval(updateStatus, 1000);

    return () => {
      clearInterval(interval);
      wsManager.off('connected', updateStatus);
      wsManager.off('disconnected', updateStatus);
    };
  }, [wsManager]);

  return (
    <div className={`connection-status ${status}`}>
      <span className="status-dot" />
      {status === 'connected' && 'Connected'}
      {status === 'disconnected' && 'Disconnected'}
      {status === 'connecting' && 'Connecting...'}
    </div>
  );
}
```

---

## Testing

### Testing WebSocket

1. **Connection check:**
   - Open the browser console
   - A "WebSocket connected" message should appear
   - Check the connection status indicator

2. **Event check:**
   - Create a new user via the API or the bot
   - A `user.created` event should appear in the console
   - The dashboard should update automatically

3. **Reconnect check:**
   - Stop the server
   - WebSocket should disconnect
   - Start the server again
   - WebSocket should reconnect automatically

### Testing webhooks

1. **Creating a webhook:**
   ```bash
   curl -X POST http://localhost:8080/webhooks \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Test Webhook",
       "url": "https://webhook.site/your-unique-url",
       "event_type": "user.created"
     }'
   ```

2. **Delivery check:**
   - Create a new user
   - Check webhook.site — a request should arrive
   - Check delivery history in the admin

3. **Signature testing:**
   - Create a webhook with a secret
   - Check the `X-Webhook-Signature` header
   - Validate the signature on the receiver side

---

## Integration checklist

- [ ] WebSocket manager created
- [ ] WebSocket connection initialized in the application
- [ ] Event handling implemented in components
- [ ] Real-time dashboard updates added
- [ ] Notifications for new events implemented
- [ ] API client for webhooks created
- [ ] Webhook create/edit form implemented
- [ ] Webhook list with filtering implemented
- [ ] Delivery history implemented
- [ ] Error handling added
- [ ] Connection status indicator added
- [ ] All features tested

---

## Additional recommendations

1. **Performance:**
   - Use debounce for frequent updates
   - Cache data that does not need real-time updates
   - Limit the number of simultaneously open WebSocket connections

2. **Security:**
   - Always use HTTPS for webhook URLs
   - Store webhook secrets in a safe place
   - Validate the signature on the receiver side
   - Restrict webhook management access (admins only)

3. **Monitoring:**
   - Log all WebSocket events
   - Track webhook delivery success
   - Set alerts for a large number of errors

4. **UX improvements:**
   - Show a loading indicator when data updates
   - Use animations for smooth updates
   - Provide a way to disable notifications
   - Add filters for events in notifications
