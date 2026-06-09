import type { SubscriptionListItem } from '../types';

const USER_UNKNOWN_PREFIX = 'user_unknown_';

export function getSubscriptionDisplayLabel(
  sub: SubscriptionListItem,
  t: (key: string, fallback: string) => string,
  isMultiTariff = false,
): string {
  let panel = (sub.panel_username ?? '').trim();
  if (panel.startsWith(USER_UNKNOWN_PREFIX)) {
    panel = '';
  }
  if (panel) return panel;

  const defaultName = t('subscription.defaultName', 'Подписка');
  if (isMultiTariff && sub.account_sequence) {
    return `${sub.tariff_name || defaultName} #${sub.account_sequence}`;
  }
  return sub.tariff_name || defaultName;
}

export function subscriptionMatchesSearch(
  sub: SubscriptionListItem,
  query: string,
  t: (key: string, fallback: string) => string,
  isMultiTariff = false,
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;

  if (getSubscriptionDisplayLabel(sub, t, isMultiTariff).toLowerCase().includes(q)) {
    return true;
  }
  if (String(sub.id).includes(q)) return true;

  const tariffName = (sub.tariff_name ?? '').trim().toLowerCase();
  if (tariffName && tariffName.includes(q)) return true;

  return false;
}

export function filterSubscriptionsByQuery(
  subscriptions: SubscriptionListItem[],
  query: string,
  t: (key: string, fallback: string) => string,
  isMultiTariff = false,
): SubscriptionListItem[] {
  const q = query.trim();
  if (!q) return subscriptions;
  return subscriptions.filter((s) => subscriptionMatchesSearch(s, q, t, isMultiTariff));
}
