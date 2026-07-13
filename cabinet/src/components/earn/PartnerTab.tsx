import { useTranslation } from 'react-i18next';

import type { PartnerInventoryStats } from '../../api/partners';
import type { PartnerStatusResponse } from '../../api/partners';
import { formatUserDate } from '../../utils/formatDate';
import {
  ClockIcon,
  ExclamationIcon,
} from '@/components/icons';

export interface PartnerTabProps {
  partnerSectionVisible: boolean;
  partnerStatus: PartnerStatusResponse | undefined;
  inventoryStats: PartnerInventoryStats | undefined;
  inventoryLoading: boolean;
  wholesalePercent: number;
  onApply: () => void;
  onBuySubscription: () => void;
  formatAmount: (amount: number) => string;
}

export function PartnerTab({
  partnerSectionVisible,
  partnerStatus,
  inventoryStats,
  inventoryLoading,
  wholesalePercent,
  onApply,
  onBuySubscription,
  formatAmount,
}: PartnerTabProps) {
  const { t, i18n } = useTranslation();

  if (!partnerSectionVisible) {
    return (
      <div className="bento-card py-12 text-center">
        <p className="text-dark-400">{t('earn.partner.sectionDisabled')}</p>
      </div>
    );
  }

  const partnerStatusValue = partnerStatus?.partner_status ?? 'none';

  if (partnerStatusValue === 'none') {
    return (
      <div className="bento-card">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-accent-500/10 text-2xl">
            🏪
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-dark-100">{t('earn.partner.heroTitle')}</h2>
            <p className="mt-1 text-sm text-dark-400">{t('earn.partner.heroDesc')}</p>
            <ul className="mt-4 space-y-2 text-sm text-dark-300">
              <li>• {t('earn.partner.benefitDiscount')}</li>
              <li>• {t('earn.partner.benefitBrand')}</li>
              <li>• {t('earn.partner.benefitStats')}</li>
            </ul>
            <button type="button" onClick={onApply} className="btn-primary mt-4 px-6">
              {t('earn.partner.applyButton')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (partnerStatusValue === 'pending') {
    return (
      <div className="bento-card border-warning-500/20">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-warning-500/10 text-warning-400">
            <ClockIcon />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-dark-100">{t('earn.partner.underReview')}</h2>
            <p className="mt-1 text-sm text-dark-400">{t('earn.partner.underReviewDesc')}</p>
            {partnerStatus?.latest_application?.created_at && (
              <p className="mt-2 text-xs text-dark-500">
                {t('earn.partner.submittedAt', {
                  date: formatUserDate(
                    partnerStatus.latest_application.created_at,
                    i18n.language,
                  ),
                })}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (partnerStatusValue === 'rejected') {
    return (
      <div className="bento-card border-error-500/20">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-error-500/10 text-error-400">
            <ExclamationIcon className="h-8 w-8" />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-dark-100">{t('earn.partner.rejected')}</h2>
            {partnerStatus?.latest_application?.admin_comment && (
              <p className="mt-1 text-sm text-dark-300">
                {partnerStatus.latest_application.admin_comment}
              </p>
            )}
            <button type="button" onClick={onApply} className="btn-primary mt-4 px-6">
              {t('earn.partner.reapplyButton')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (partnerStatusValue === 'approved') {
    const stats = inventoryStats;

    return (
      <div className="space-y-6">
        <div className="bento-card border-success-500/20">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-success-500/10 text-2xl">
                ✅
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-dark-100">
                  {t('earn.partner.activeStatus')}
                </h2>
                {partnerStatus?.panel_brand_prefix && (
                  <p className="mt-2 text-sm text-dark-300">
                    🏷 {t('earn.partner.brandLabel')}: {partnerStatus.panel_brand_prefix}
                  </p>
                )}
              </div>
            </div>
            {wholesalePercent > 0 && (
              <span className="btn-secondary shrink-0 self-start px-4 py-2 text-sm font-medium">
                {t('earn.partner.discountBadge', { percent: wholesalePercent })}
              </span>
            )}
          </div>
        </div>

        <div className="bento-card">
          <h3 className="mb-4 text-lg font-semibold text-dark-100">{t('earn.partner.statsTitle')}</h3>
          {inventoryLoading ? (
            <div className="flex min-h-24 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
            </div>
          ) : (
            <>
              <div className="mb-4 rounded-xl bg-dark-800/30 p-4">
                <div className="text-sm text-dark-500">{t('earn.partner.statTotal')}</div>
                <div className="stat-value mt-1">{stats?.total_subscriptions ?? 0}</div>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-xl bg-dark-800/30 p-3">
                  <div className="text-sm text-dark-500">🟢 {t('earn.partner.statActive')}</div>
                  <div className="mt-1 text-lg font-semibold text-success-400">
                    {stats?.active_subscriptions ?? 0}
                  </div>
                </div>
                <div className="rounded-xl bg-dark-800/30 p-3">
                  <div className="text-sm text-dark-500">🔴 {t('earn.partner.statExpired')}</div>
                  <div className="mt-1 text-lg font-semibold text-dark-100">
                    {stats?.expired_subscriptions ?? 0}
                  </div>
                </div>
                <div className="rounded-xl bg-dark-800/30 p-3">
                  <div className="text-sm text-dark-500">🟡 {t('earn.partner.statNearExpiry')}</div>
                  <div className="mt-1 text-lg font-semibold text-warning-400">
                    {stats?.near_expiry_subscriptions ?? 0}
                  </div>
                </div>
                <div className="rounded-xl bg-dark-800/30 p-3">
                  <div className="text-sm text-dark-500">🟢 {t('earn.partner.statOnline')}</div>
                  <div className="mt-1 text-lg font-semibold text-accent-400">
                    {stats?.online_users ?? 0}
                  </div>
                  <div className="mt-0.5 text-xs text-dark-500">
                    {t('earn.partner.statOnlineHint', {
                      active: stats?.active_subscriptions ?? 0,
                    })}
                  </div>
                </div>
              </div>
              <div className="mt-4 rounded-xl bg-dark-800/30 p-4">
                <div className="text-sm font-medium text-dark-300">{t('earn.partner.statWalletSpent')}</div>
                <div className="mt-2 text-2xl font-bold text-dark-100">
                  {formatAmount(stats?.total_spent_rubles ?? 0)}
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-dark-800/50 p-3">
                    <div className="text-xs text-dark-500">{t('earn.partner.statPurchaseWeek')}</div>
                    <div className="mt-1 text-sm font-semibold text-dark-200">
                      {formatAmount(stats?.spent_week_rubles ?? 0)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-dark-800/50 p-3">
                    <div className="text-xs text-dark-500">{t('earn.partner.statPurchaseMonth')}</div>
                    <div className="mt-1 text-sm font-semibold text-dark-200">
                      {formatAmount(stats?.spent_month_rubles ?? 0)}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
          <button type="button" onClick={onBuySubscription} className="btn-primary mt-4 w-full px-6 sm:w-auto">
            {t('earn.partner.buySubscription')}
          </button>
        </div>
      </div>
    );
  }

  return null;
}
