import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Navigate, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ClipboardIcon,
  PlusIcon,
  SearchIcon,
  XIcon,
} from '@/components/icons';
import { subscriptionApi } from '../api/subscription';
import { balanceApi } from '../api/balance';
import { useTheme } from '../hooks/useTheme';
import { getGlassColors } from '../utils/glassTheme';
import { useAuthStore } from '../store/auth';
import SubscriptionListCard from '../components/subscription/SubscriptionListCard';
import TrialOfferCard from '../components/dashboard/TrialOfferCard';

const PAGE_LIMIT = 10;

function EmptyState({ onBuy }: { onBuy: () => void }) {
  const { t } = useTranslation();
  const { isDark } = useTheme();
  const g = getGlassColors(isDark);

  return (
    <div
      className="rounded-2xl border p-10 text-center"
      style={{ background: g.cardBg, borderColor: g.cardBorder }}
    >
      <div
        className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl"
        style={{ background: g.innerBg }}
      >
        <ClipboardIcon className="h-8 w-8 opacity-40" />
      </div>
      <h3 className="mb-2 text-xl font-semibold" style={{ color: g.text }}>
        {t('subscriptions.empty', 'Нет подписок')}
      </h3>
      <p className="mb-6 text-sm" style={{ color: g.textSecondary }}>
        {t('subscriptions.emptyDesc', 'У вас пока нет активных подписок')}
      </p>
      <button
        onClick={onBuy}
        className="rounded-xl bg-accent-500 px-8 py-3 text-sm font-medium text-white transition-colors hover:bg-accent-600"
      >
        {t('subscriptions.buy', 'Купить подписку')}
      </button>
    </div>
  );
}

export default function Subscriptions() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const g = getGlassColors(isDark);
  const queryClient = useQueryClient();
  const refreshUser = useAuthStore((state) => state.refreshUser);
  const [trialError, setTrialError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const { data: summaryData } = useQuery({
    queryKey: ['subscriptions-list-summary'],
    queryFn: () => subscriptionApi.getSubscriptions({ limit: 100 }),
    staleTime: 30_000,
    refetchOnMount: 'always',
  });

  const { data, isLoading } = useQuery({
    queryKey: ['subscriptions-list', offset, PAGE_LIMIT, debouncedSearch],
    queryFn: () =>
      subscriptionApi.getSubscriptions({
        offset,
        limit: PAGE_LIMIT,
        search: debouncedSearch.trim() || undefined,
      }),
    staleTime: 30_000,
    refetchOnMount: 'always',
  });

  const subscriptions = data?.subscriptions ?? [];
  const total = data?.total ?? 0;
  const isMultiTariff = data?.multi_tariff_enabled ?? summaryData?.multi_tariff_enabled ?? false;
  const accountTotal = summaryData?.total ?? 0;
  const hasNoSubscriptions = accountTotal === 0;
  const hasActivePaid = (summaryData?.subscriptions ?? []).some(
    (s) => !s.is_trial && (s.status === 'active' || s.status === 'limited'),
  );

  const showSearch = accountTotal >= 2 && !isLoading;
  const totalPages = Math.ceil(total / PAGE_LIMIT) || 1;
  const currentPage = Math.floor(offset / PAGE_LIMIT) + 1;

  const { data: trialInfo, isLoading: trialLoading } = useQuery({
    queryKey: ['trial-info'],
    queryFn: () => subscriptionApi.getTrialInfo(),
    enabled: hasNoSubscriptions,
    staleTime: 30_000,
  });

  const { data: balanceData } = useQuery({
    queryKey: ['balance'],
    queryFn: balanceApi.getBalance,
    enabled: hasNoSubscriptions && !!trialInfo?.is_available,
    staleTime: 30_000,
  });

  const activateTrialMutation = useMutation({
    mutationFn: () => subscriptionApi.activateTrial(),
    onSuccess: () => {
      setTrialError(null);
      queryClient.invalidateQueries({ queryKey: ['subscription'] });
      queryClient.invalidateQueries({ queryKey: ['subscriptions-list'] });
      queryClient.invalidateQueries({ queryKey: ['subscriptions-list-summary'] });
      queryClient.invalidateQueries({ queryKey: ['trial-info'] });
      queryClient.invalidateQueries({ queryKey: ['balance'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-options'] });
      refreshUser();
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      setTrialError(error.response?.data?.detail || t('common.error'));
    },
  });

  if (
    summaryData &&
    !summaryData.multi_tariff_enabled &&
    summaryData.total === 1 &&
    summaryData.subscriptions[0]
  ) {
    return <Navigate to={`/subscriptions/${summaryData.subscriptions[0].id}`} replace />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ color: g.text }}>
          {t('subscriptions.title', 'Мои подписки')}
        </h1>
        {!isLoading && hasActivePaid && (
          <button
            onClick={() => navigate('/subscription/purchase')}
            className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-medium transition-colors"
            style={{
              background: 'rgba(var(--color-accent-400), 0.1)',
              color: 'rgb(var(--color-accent-400))',
              border: '1px solid rgba(var(--color-accent-400), 0.2)',
            }}
          >
            <PlusIcon className="h-4 w-4" />
            {t('subscriptions.buyAnother', 'Новый тариф')}
          </button>
        )}
      </div>

      {showSearch && (
        <div className="space-y-2">
          <div className="relative">
            <div
              className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5"
              style={{ color: g.textSecondary }}
            >
              <SearchIcon className="h-4 w-4 opacity-60" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t(
                'subscriptions.searchPlaceholder',
                'Поиск: имя на карточке, тариф или ID',
              )}
              className="w-full rounded-2xl border py-3 pl-10 pr-10 text-sm transition-colors focus:outline-none focus:ring-1"
              style={{
                background: g.cardBg,
                borderColor: g.cardBorder,
                color: g.text,
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 right-0 flex items-center pr-3.5 transition-opacity hover:opacity-80"
                style={{ color: g.textSecondary }}
                aria-label={t('subscriptions.searchClear', 'Очистить поиск')}
              >
                <XIcon className="h-4 w-4" />
              </button>
            )}
          </div>
          {searchQuery.trim() && (
            <p className="text-xs" style={{ color: g.textSecondary }}>
              {t('subscriptions.searchActive', { query: searchQuery })}
            </p>
          )}
        </div>
      )}

      {!isLoading && accountTotal > 0 && !hasActivePaid && (
        <button
          onClick={() => navigate('/subscription/purchase')}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-accent-500 p-3.5 text-sm font-semibold text-white transition-colors hover:bg-accent-600"
        >
          <PlusIcon className="h-5 w-5" />
          {t('subscriptions.browsePlans', 'Посмотреть тарифы и купить подписку')}
        </button>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-36 animate-pulse rounded-2xl"
              style={{ background: g.innerBg }}
            />
          ))}
        </div>
      )}

      {hasNoSubscriptions && !trialLoading && trialInfo?.is_available && (
        <div className="space-y-4">
          <TrialOfferCard
            trialInfo={trialInfo}
            balanceKopeks={balanceData?.balance_kopeks ?? 0}
            balanceRubles={balanceData?.balance_rubles ?? 0}
            activateTrialMutation={activateTrialMutation}
            trialError={trialError}
          />
          <button
            onClick={() => navigate('/subscription/purchase')}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600"
          >
            <PlusIcon className="h-5 w-5" />
            {t('subscriptions.browsePlans', 'Посмотреть тарифы и купить подписку')}
          </button>
        </div>
      )}
      {hasNoSubscriptions && !trialLoading && !trialInfo?.is_available && (
        <EmptyState onBuy={() => navigate('/subscription/purchase')} />
      )}

      {accountTotal > 0 && subscriptions.length === 0 && debouncedSearch.trim() && !isLoading && (
        <div
          className="rounded-2xl border p-8 text-center"
          style={{ background: g.cardBg, borderColor: g.cardBorder }}
        >
          <p className="mb-4 text-sm" style={{ color: g.textSecondary }}>
            {t('subscriptions.searchNoResults', 'Подписки по этому запросу не найдены')}
          </p>
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            className="rounded-xl px-4 py-2 text-sm font-medium transition-colors"
            style={{
              background: g.innerBg,
              color: g.text,
              border: `1px solid ${g.cardBorder}`,
            }}
          >
            {t('subscriptions.searchClear', 'Очистить поиск')}
          </button>
        </div>
      )}

      {subscriptions.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:[&>*:last-child:nth-child(odd)]:col-span-2">
          {subscriptions.map((sub) => (
            <SubscriptionListCard
              key={sub.id}
              subscription={sub}
              isMultiTariff={isMultiTariff}
              onClick={() => navigate(`/subscriptions/${sub.id}`)}
            />
          ))}
        </div>
      )}

      {total > PAGE_LIMIT && (
        <div className="flex items-center justify-between">
          <div className="text-sm" style={{ color: g.textSecondary }}>
            {t('admin.users.pagination.showing', {
              from: total === 0 ? 0 : offset + 1,
              to: Math.min(offset + PAGE_LIMIT, total),
              total,
            })}
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setOffset(Math.max(0, offset - PAGE_LIMIT))}
                disabled={offset === 0}
                className="rounded-lg border p-2 transition-colors disabled:opacity-50"
                style={{ borderColor: g.cardBorder, background: g.cardBg }}
              >
                <ChevronLeftIcon />
              </button>
              <span className="px-3 py-2 text-sm" style={{ color: g.text }}>
                {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setOffset(offset + PAGE_LIMIT)}
                disabled={offset + PAGE_LIMIT >= total}
                className="rounded-lg border p-2 transition-colors disabled:opacity-50"
                style={{ borderColor: g.cardBorder, background: g.cardBg }}
              >
                <ChevronRightIcon />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
