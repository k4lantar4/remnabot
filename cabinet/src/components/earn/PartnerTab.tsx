import { useTranslation } from 'react-i18next';

import type { PartnerStatusResponse } from '../../api/partners';
import { CampaignCard } from '../partner/CampaignCard';
import { aggregatePartnerStats } from '../../utils/earnStats';
import { formatUserDate } from '../../utils/formatDate';
import {
  ClockIcon,
  ExclamationIcon,
  LinkIcon,
} from '@/components/icons';

export interface PartnerTabProps {
  partnerSectionVisible: boolean;
  partnerStatus: PartnerStatusResponse | undefined;
  aggregatedStats: ReturnType<typeof aggregatePartnerStats>;
  wholesalePercent: number;
  onApply: () => void;
  onGoToInvite: () => void;
  formatEarnings: (kopeks: number) => string;
}

export function PartnerTab({
  partnerSectionVisible,
  partnerStatus,
  aggregatedStats,
  wholesalePercent,
  onApply,
  onGoToInvite,
  formatEarnings,
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
    return (
      <div className="space-y-6">
        <div className="bento-card border-success-500/20">
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
              {wholesalePercent > 0 && (
                <p className="mt-1 text-sm text-dark-300">
                  💰 {t('earn.partner.discountLabel')}: {wholesalePercent}%
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="bento-card">
          <h3 className="mb-4 text-lg font-semibold text-dark-100">{t('earn.partner.statsTitle')}</h3>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <div className="rounded-xl bg-dark-800/30 p-3">
              <div className="text-sm text-dark-500">{t('earn.partner.statRegistrations')}</div>
              <div className="mt-1 text-lg font-semibold text-dark-100">
                {aggregatedStats.registrations}
              </div>
            </div>
            <div className="rounded-xl bg-dark-800/30 p-3">
              <div className="text-sm text-dark-500">{t('earn.partner.statReferrals')}</div>
              <div className="mt-1 text-lg font-semibold text-dark-100">
                {aggregatedStats.referrals}
              </div>
            </div>
            <div className="rounded-xl bg-dark-800/30 p-3">
              <div className="text-sm text-dark-500">{t('earn.partner.statEarnings')}</div>
              <div className="mt-1 text-lg font-semibold text-success-400">
                {formatEarnings(aggregatedStats.earningsKopeks)}
              </div>
            </div>
          </div>
          <button type="button" onClick={onGoToInvite} className="btn-secondary mt-4 px-6">
            {t('earn.partner.goToInvite')} ←
          </button>
        </div>

        {partnerStatus?.campaigns && partnerStatus.campaigns.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-500/10 text-accent-400">
                <LinkIcon />
              </div>
              <h2 className="text-lg font-semibold text-dark-100">
                {t('earn.partner.yourCampaigns')}
              </h2>
            </div>
            {partnerStatus.campaigns.map((campaign) => (
              <CampaignCard key={campaign.id} campaign={campaign} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return null;
}
