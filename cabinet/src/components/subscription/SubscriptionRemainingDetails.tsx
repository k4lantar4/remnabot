import { useTranslation } from 'react-i18next';
import { formatUserDate } from '../../utils/formatDate';
import { getGlassColors } from '../../utils/glassTheme';
import { getSubscriptionStatusLabel } from '../../utils/subscriptionStatusDisplay';
import type { Subscription } from '../../types';

type TranslateFn = ReturnType<typeof useTranslation>['t'];

function formatDaysHoursLeft(subscription: Subscription, t: TranslateFn): string {
  if (subscription.is_expired) return t('subscription.expired');
  const days = Math.max(0, subscription.days_left || 0);
  const hours = Math.max(0, subscription.hours_left || 0);
  if (days <= 0 && hours <= 0) return t('subscription.expired');
  if (days > 0 && hours > 0) {
    return `${t('subscription.days', { count: days })} ${hours}${t('subscription.hours')}`;
  }
  if (days > 0) return t('subscription.days', { count: days });
  return `${hours}${t('subscription.hours')}`;
}

export interface SubscriptionRemainingDetailsProps {
  subscription: Subscription;
  usedGb: number;
  isUnlimited: boolean;
  connectedDevices: number;
  glassColors: ReturnType<typeof getGlassColors>;
  accentHex: string;
}

export function SubscriptionRemainingDetails({
  subscription,
  usedGb,
  isUnlimited,
  connectedDevices,
  glassColors: g,
  accentHex,
}: SubscriptionRemainingDetailsProps) {
  const { t, i18n } = useTranslation();
  const remainingGb =
    isUnlimited || subscription.traffic_limit_gb === 0
      ? null
      : Math.max(0, subscription.traffic_limit_gb - usedGb);

  const rows: { emoji: string; label: string; value: string }[] = [
    {
      emoji: '🔘',
      label: t('subscription.status', 'وضعیت'),
      value: getSubscriptionStatusLabel(subscription, t),
    },
    {
      emoji: '🗓️',
      label: t('subscription.expiresAt'),
      value: formatUserDate(subscription.end_date, i18n.language),
    },
    {
      emoji: '⏳',
      label: t('dashboard.remaining'),
      value: formatDaysHoursLeft(subscription, t),
    },
    {
      emoji: '📊',
      label: t('subscription.trafficUsed', 'ترافیک مصرفی'),
      value: isUnlimited
        ? `${usedGb.toFixed(1)} ${t('common.units.gb')}`
        : `${usedGb.toFixed(1)} / ${subscription.traffic_limit_gb} ${t('common.units.gb')}`,
    },
  ];

  if (!isUnlimited && remainingGb != null) {
    rows.push({
      emoji: '🧩',
      label: t('subscription.remainingTraffic', 'ترافیک باقی‌مانده'),
      value: `${remainingGb.toFixed(1)} ${t('common.units.gb')}`,
    });
  }

  if (subscription.start_date) {
    rows.push({
      emoji: '🧾',
      label: t('subscription.purchaseDate', 'تاریخ خرید'),
      value: formatUserDate(subscription.start_date, i18n.language),
    });
  }

  if (subscription.tariff_name) {
    rows.push({
      emoji: '🏷️',
      label: t('subscription.tariffName', 'نام سرویس'),
      value: subscription.tariff_name,
    });
  }

  rows.push({
    emoji: '👥',
    label: t('subscription.deviceUsage', 'کاربر / اتصال'),
    value:
      subscription.device_limit === 0
        ? `${connectedDevices} / ∞`
        : `${connectedDevices} / ${subscription.device_limit}`,
  });

  const isExpired = subscription.is_expired;
  const isUrgent = !isExpired && subscription.days_left <= 3 && !subscription.user_disabled;

  return (
    <div
      className="min-w-0 overflow-hidden rounded-[14px] p-3.5"
      style={{
        background: isExpired
          ? 'rgba(255,59,92,0.06)'
          : subscription.user_disabled
            ? `${accentHex}08`
            : isUrgent
              ? 'rgba(255,184,0,0.06)'
              : g.innerBg,
        border: isExpired
          ? '1px solid rgba(255,59,92,0.15)'
          : subscription.user_disabled
            ? `1px solid ${accentHex}25`
            : isUrgent
              ? '1px solid rgba(255,184,0,0.15)'
              : `1px solid ${g.innerBorder}`,
      }}
    >
      <div
        className="mb-3 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider"
        style={{ color: g.textSecondary }}
      >
        <span aria-hidden="true">📋</span>
        {t('subscription.detailsTitle', 'جزئیات اشتراک')}
      </div>
      <div className="grid grid-cols-1 gap-2 text-[12px]">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-3">
            <span className="shrink-0 text-dark-50/70">
              {row.emoji} {row.label}
            </span>
            <span className="truncate text-end font-mono tabular-nums text-dark-50/85">
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
