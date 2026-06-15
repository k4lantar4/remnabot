import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  partnerApi,
  type AdminPartnerItem,
  type AdminPartnerApplicationItem,
} from '../api/partners';
import { AdminBackButton } from '../components/admin';
import { useCurrency } from '../hooks/useCurrency';
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  RefreshIcon,
  SearchIcon,
  SettingsIcon,
  TelegramSmallIcon as TelegramIcon,
} from '@/components/icons';

const PAGE_LIMIT = 20;

interface PartnerRowProps {
  partner: AdminPartnerItem;
  onOpenDetail: () => void;
  formatAmount: (amount: number) => string;
}

function PartnerRow({ partner, onOpenDetail, formatAmount }: PartnerRowProps) {
  const { t } = useTranslation();

  return (
    <div className="rounded-xl border border-dark-700 bg-dark-800/50 p-3 sm:p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-4">
        {/* Partner info */}
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={onOpenDetail}
              className="truncate text-left font-medium text-dark-100 hover:text-accent-400"
            >
              {partner.first_name || partner.username || `#${partner.user_id}`}
            </button>
            {partner.username && (
              <span className="shrink-0 text-sm text-dark-500">@{partner.username}</span>
            )}
          </div>
          {partner.telegram_id != null && (
            <div className="mb-1 flex items-center gap-1 text-xs text-dark-400">
              <TelegramIcon />
              <span className="truncate">{partner.telegram_id}</span>
            </div>
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-dark-400">
            <span>{t('admin.partners.referrals', { count: partner.total_referrals })}</span>
            <span className="text-success-400">
              {formatAmount(partner.total_earnings_kopeks / 100)}
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenDetail}
          className="self-end rounded-lg p-2 text-dark-500 transition-colors hover:bg-dark-700 hover:text-dark-300 lg:self-center"
          aria-label={t('admin.partners.actions.review')}
        >
          <ChevronRightIcon className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}

export default function AdminPartners() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { formatWithCurrency } = useCurrency();

  const [activeTab, setActiveTab] = useState<'partners' | 'applications'>('partners');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);

  const { data: stats, refetch: refetchStats } = useQuery({
    queryKey: ['admin-partner-stats'],
    queryFn: () => partnerApi.getStats(),
  });

  const {
    data: partnersData,
    isLoading: partnersLoading,
    refetch: refetchPartners,
  } = useQuery({
    queryKey: ['admin-partners', offset, PAGE_LIMIT, search],
    queryFn: () =>
      partnerApi.getPartners({
        offset,
        limit: PAGE_LIMIT,
        search: search.trim() || undefined,
      }),
    enabled: activeTab === 'partners',
  });

  const { data: applicationsData, isLoading: applicationsLoading } = useQuery({
    queryKey: ['admin-partner-applications'],
    queryFn: () => partnerApi.getApplications({ status: 'pending' }),
  });

  const partners = partnersData?.items || [];
  const total = partnersData?.total ?? 0;
  const applications = applicationsData?.items || [];

  const totalPages = Math.ceil(total / PAGE_LIMIT) || 1;
  const currentPage = Math.floor(offset / PAGE_LIMIT) + 1;

  const handleRefresh = () => {
    refetchStats();
    refetchPartners();
  };

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <AdminBackButton to="/admin" />
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-dark-100">{t('admin.partners.title')}</h1>
          <p className="text-sm text-dark-400">{t('admin.partners.subtitle')}</p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          className="rounded-lg p-2 text-dark-400 transition-colors hover:bg-dark-800 hover:text-dark-200"
          title={t('common.refresh')}
        >
          <RefreshIcon className={partnersLoading ? 'animate-spin' : ''} />
        </button>
        <button
          type="button"
          onClick={() => navigate('/admin/partners/settings')}
          className="rounded-lg bg-dark-800 p-2 text-dark-400 transition-colors hover:bg-dark-700 hover:text-dark-200"
          title={t('admin.partners.settings')}
        >
          <SettingsIcon className="h-5 w-5" />
        </button>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-dark-700 bg-dark-800 p-4">
            <div className="text-2xl font-bold text-dark-100">{stats.total_partners}</div>
            <div className="text-sm text-dark-400">{t('admin.partners.totalPartners')}</div>
          </div>
          <div className="rounded-xl border border-dark-700 bg-dark-800 p-4">
            <div className="text-2xl font-bold text-accent-400">{stats.pending_applications}</div>
            <div className="text-sm text-dark-400">{t('admin.partners.pendingApplications')}</div>
          </div>
          <div className="rounded-xl border border-dark-700 bg-dark-800 p-4">
            <div className="text-2xl font-bold text-dark-100">{stats.total_referrals}</div>
            <div className="text-sm text-dark-400">{t('admin.partners.totalReferrals')}</div>
          </div>
          <div className="rounded-xl border border-dark-700 bg-dark-800 p-4">
            <div className="text-2xl font-bold text-success-400">
              {formatWithCurrency(stats.total_earnings_kopeks / 100)}
            </div>
            <div className="text-sm text-dark-400">{t('admin.partners.totalEarnings')}</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-4 flex gap-1 rounded-lg border border-dark-700 bg-dark-800/40 p-1">
        <button
          type="button"
          onClick={() => setActiveTab('partners')}
          className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'partners'
              ? 'bg-dark-700 text-dark-100'
              : 'text-dark-400 hover:text-dark-200'
          }`}
        >
          {t('admin.partners.tabs.partners')}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('applications')}
          className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'applications'
              ? 'bg-dark-700 text-dark-100'
              : 'text-dark-400 hover:text-dark-200'
          }`}
        >
          {t('admin.partners.tabs.applications')}
          {applications.length > 0 && (
            <span className="ml-2 rounded-full bg-accent-500/20 px-2 py-0.5 text-xs text-accent-400">
              {applications.length}
            </span>
          )}
        </button>
      </div>

      {/* Partners Tab */}
      {activeTab === 'partners' && (
        <>
          <div className="mb-4">
            <div className="relative">
              <input
                type="text"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setOffset(0);
                }}
                placeholder={t('admin.partners.search')}
                className="w-full rounded-xl border border-dark-700 bg-dark-800 py-2 pl-10 pr-4 text-dark-100 placeholder-dark-500 focus:border-dark-600 focus:outline-none"
              />
              <div className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-500">
                <SearchIcon />
              </div>
            </div>
          </div>

          {partnersLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
            </div>
          ) : partners.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-dark-400">{t('admin.partners.noPartners')}</p>
            </div>
          ) : (
            <div className="mb-4 space-y-3">
              {partners.map((partner: AdminPartnerItem) => (
                <PartnerRow
                  key={partner.user_id}
                  partner={partner}
                  onOpenDetail={() => navigate(`/admin/partners/${partner.user_id}`)}
                  formatAmount={(amount) => formatWithCurrency(amount)}
                />
              ))}
            </div>
          )}

          {total > 0 && (
            <div className="flex items-center justify-between">
              <div className="text-sm text-dark-400">
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
                    className="rounded-lg border border-dark-700 bg-dark-800 p-2 transition-colors hover:bg-dark-700 disabled:opacity-50"
                  >
                    <ChevronLeftIcon />
                  </button>
                  <span className="px-3 py-2 text-dark-300">
                    {currentPage} / {totalPages}
                  </span>
                  <button
                    type="button"
                    onClick={() => setOffset(offset + PAGE_LIMIT)}
                    disabled={offset + PAGE_LIMIT >= total}
                    className="rounded-lg border border-dark-700 bg-dark-800 p-2 transition-colors hover:bg-dark-700 disabled:opacity-50"
                  >
                    <ChevronRightIcon />
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Applications Tab */}
      {activeTab === 'applications' && (
        <>
          {applicationsLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
            </div>
          ) : applications.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-dark-400">{t('admin.partners.noApplications')}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {applications.map((app: AdminPartnerApplicationItem) => (
                <div key={app.id} className="rounded-xl border border-dark-700 bg-dark-800 p-4">
                  <div className="mb-3 flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex min-w-0 items-center gap-2">
                        <h3 className="truncate font-medium text-dark-100">
                          {app.first_name || app.username || `#${app.user_id}`}
                        </h3>
                        {app.username && (
                          <span className="shrink-0 text-sm text-dark-500">@{app.username}</span>
                        )}
                      </div>
                      {app.company_name && (
                        <div className="text-sm text-dark-300">{app.company_name}</div>
                      )}
                    </div>
                  </div>

                  <div className="mb-3 space-y-1 text-sm text-dark-400">
                    {app.website_url && (
                      <div>
                        {t('admin.partners.applicationFields.website')}: {app.website_url}
                      </div>
                    )}
                    {app.telegram_channel && (
                      <div>
                        {t('admin.partners.applicationFields.channel')}: {app.telegram_channel}
                      </div>
                    )}
                    {app.description && (
                      <div>
                        {t('admin.partners.applicationFields.description')}: {app.description}
                      </div>
                    )}
                    {app.expected_monthly_referrals != null && (
                      <div>
                        {t('admin.partners.applicationFields.expectedReferrals')}:{' '}
                        {app.expected_monthly_referrals}
                      </div>
                    )}
                    {app.desired_commission_percent != null && (
                      <div>
                        {t('admin.partners.applicationFields.desiredCommission')}:{' '}
                        {app.desired_commission_percent}%
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        navigate(`/admin/partners/applications/${app.id}/review`, {
                          state: { application: app },
                        })
                      }
                      className="flex-1 rounded-lg bg-accent-500/20 px-4 py-2 text-sm font-medium text-accent-400 transition-colors hover:bg-accent-500/30"
                    >
                      {t('admin.partners.actions.review')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
