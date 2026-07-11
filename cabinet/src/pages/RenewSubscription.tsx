import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useNavigate, useParams } from 'react-router';
import { subscriptionApi } from '../api/subscription';
import { useTheme } from '../hooks/useTheme';
import { getGlassColors } from '../utils/glassTheme';
import { useCurrency } from '../hooks/useCurrency';
import { WebBackButton } from '../components/WebBackButton';
import { TariffPurchaseForm } from '../components/subscription/purchase/TariffPurchaseForm';
import type { TariffsPurchaseOptions } from '../types';

export default function RenewSubscription() {
  const { subscriptionId } = useParams<{ subscriptionId: string }>();
  const subId = subscriptionId ? Number(subscriptionId) : undefined;

  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const g = getGlassColors(isDark);
  const { formatAmount, currencySymbol } = useCurrency();

  const { data: subscriptionResponse, isLoading: subscriptionLoading } = useQuery({
    queryKey: ['subscription', subId],
    queryFn: () => subscriptionApi.getSubscription(subId),
    enabled: !!subId,
    staleTime: 30_000,
  });
  const subscription = subscriptionResponse?.subscription ?? null;

  const { data: purchaseOptions, isLoading: optionsLoading } = useQuery({
    queryKey: ['purchase-options', subId],
    queryFn: () => subscriptionApi.getPurchaseOptions(subId),
    staleTime: 0,
    refetchOnMount: 'always',
  });

  const balanceKopeks = purchaseOptions?.balance_kopeks ?? 0;
  const isLoading = subscriptionLoading || optionsLoading;

  if (!subId) {
    return <Navigate to="/subscriptions" replace />;
  }

  if (isLoading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
      </div>
    );
  }

  if (subscription && !subscription.tariff_id) {
    return <Navigate to={`/subscription/purchase?subscriptionId=${subId}`} replace />;
  }

  const isTariffsMode = purchaseOptions?.sales_mode === 'tariffs';
  const tariffs =
    isTariffsMode && purchaseOptions
      ? (purchaseOptions as TariffsPurchaseOptions).tariffs
      : [];
  const tariff = subscription?.tariff_id
    ? tariffs.find((item) => item.id === subscription.tariff_id)
    : undefined;

  const renewalTrafficGb = subscription?.traffic_limit_gb;
  const renewalUnlimited = renewalTrafficGb === 0;
  const renewalTrafficLabel = renewalUnlimited
    ? t('subscription.unlimitedTraffic', 'ترافیک نامحدود')
    : renewalTrafficGb != null && renewalTrafficGb > 0
      ? t('subscription.summary.traffic', 'حجم: {{gb}} گیگ', { gb: renewalTrafficGb })
      : null;

  const initialTrafficGb =
    renewalTrafficGb != null && renewalTrafficGb > 0 ? renewalTrafficGb : undefined;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <WebBackButton to={`/subscriptions/${subId}`} />
        <div>
          <h1 className="text-2xl font-bold" style={{ color: g.text }}>
            {t('subscription.extend', 'Продлить подписку')}
          </h1>
          {subscription?.tariff_name && (
            <p className="mt-1 text-sm" style={{ color: g.textSecondary }}>
              {subscription.tariff_name}
              {renewalTrafficLabel ? ` · ${renewalTrafficLabel}` : ''}
            </p>
          )}
        </div>
      </div>

      <div
        className="flex items-center justify-between rounded-2xl p-4"
        style={{ background: g.cardBg, border: `1px solid ${g.cardBorder}` }}
      >
        <span className="text-sm" style={{ color: g.textSecondary }}>
          {t('common.balance', 'Баланс')}
        </span>
        <span className="text-base font-semibold" style={{ color: g.text }}>
          {formatAmount(i18n.language === 'fa' ? balanceKopeks : balanceKopeks / 100)}{' '}
          {currencySymbol}
        </span>
      </div>

      {!tariff ? (
        <div
          className="rounded-2xl p-6 text-center"
          style={{ background: g.cardBg, border: `1px solid ${g.cardBorder}` }}
        >
          <p className="mb-4" style={{ color: g.textSecondary }}>
            {t('subscription.noRenewalOptions', 'Нет доступных вариантов продления')}
          </p>
          <Link
            to={`/subscription/purchase?subscriptionId=${subId}`}
            className="inline-block rounded-xl bg-accent-500 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-600"
          >
            {t('subscription.getSubscription', 'Получить подписку')}
          </Link>
        </div>
      ) : (
        <TariffPurchaseForm
          key={`${tariff.id}-${initialTrafficGb ?? 'default'}`}
          tariff={tariff}
          subscriptionId={subId}
          balanceKopeks={purchaseOptions?.balance_kopeks}
          initialTrafficGb={initialTrafficGb}
          onBack={() => navigate(`/subscriptions/${subId}`)}
        />
      )}
    </div>
  );
}
