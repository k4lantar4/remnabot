import type { TFunction } from 'i18next';
import type { Subscription } from '../types';

export function getSubscriptionStatusLabel(
  subscription: Subscription,
  t: TFunction,
): string {
  if (subscription.is_active) {
    return subscription.is_trial
      ? t('subscription.trialStatus', 'دوره آزمایشی')
      : t('subscription.statusActive', t('subscription.active', 'فعال'));
  }
  if (subscription.user_disabled) {
    return t('subscription.statusUserDisabled', 'خاموش شده');
  }
  if (subscription.is_limited) {
    return t('subscription.statusLimited', t('subscription.trafficLimited', 'ترافیک تمام شده'));
  }
  if (subscription.status === 'disabled') {
    return t('subscription.inactive', 'غیرفعال');
  }
  return t('subscription.statusExpired', t('subscription.expired', 'منقضی شده'));
}

export function getSubscriptionStatusStyle(subscription: Subscription, zoneMainHex: string) {
  if (subscription.is_active) {
    return {
      background: `${zoneMainHex}15`,
      border: `1px solid ${zoneMainHex}30`,
      color: zoneMainHex,
    };
  }
  if (subscription.user_disabled) {
    return {
      background: `${zoneMainHex}10`,
      border: `1px solid ${zoneMainHex}28`,
      color: zoneMainHex,
    };
  }
  if (subscription.is_limited) {
    return {
      background: 'rgba(255,184,0,0.12)',
      border: '1px solid rgba(255,184,0,0.25)',
      color: 'rgb(var(--color-urgent-400))',
    };
  }
  return {
    background: 'rgba(255,59,92,0.12)',
    border: '1px solid rgba(255,59,92,0.25)',
    color: 'rgb(var(--color-critical-500))',
  };
}
