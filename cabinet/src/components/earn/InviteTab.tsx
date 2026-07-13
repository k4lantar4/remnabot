import { useTranslation } from 'react-i18next';

import type { PartnerCampaignInfo } from '../../api/partners';
import { usePlatform } from '../../platform';
import { useCurrency } from '../../hooks/useCurrency';
import { formatUserDate } from '../../utils/formatDate';
import type { PaginatedResponse } from '../../types';
import { CampaignCard } from '../partner/CampaignCard';
import { CheckIcon, CopyIcon, LinkIcon, ShareIcon, TelegramIcon, UsersIcon } from '@/components/icons';

interface ReferralListItem {
  id: number;
  username: string | null;
  first_name: string | null;
  created_at: string;
  has_paid: boolean;
}

export interface InviteTabProps {
  botReferralLink: string;
  referralCreditRubles: number;
  commissionPercent: number;
  brandingName: string;
  referralList: PaginatedResponse<ReferralListItem> | undefined;
  campaigns: PartnerCampaignInfo[] | undefined;
  onCopy: (link: string) => void;
  copied: boolean;
}

export function InviteTab({
  botReferralLink,
  referralCreditRubles,
  commissionPercent,
  brandingName,
  referralList,
  campaigns,
  onCopy,
  copied,
}: InviteTabProps) {
  const { t, i18n } = useTranslation();
  const { formatWithCurrency } = useCurrency();
  const { openTelegramLink } = usePlatform();

  const shareLink = () => {
    if (!botReferralLink) return;
    const shareText = t('earn.invite.shareMessage', { botName: brandingName });

    if (navigator.share) {
      navigator
        .share({
          title: t('earn.title'),
          text: shareText,
          url: botReferralLink,
        })
        .catch(() => {});
      return;
    }

    const telegramUrl = `https://t.me/share/url?url=${encodeURIComponent(
      botReferralLink,
    )}&text=${encodeURIComponent(shareText)}`;
    openTelegramLink(telegramUrl);
  };

  return (
    <div className="space-y-6">
      {/* Referral credit */}
      <div className="bento-card">
        <div className="text-sm text-dark-400">{t('earn.invite.referralCredit')}</div>
        <div className="mt-1 text-2xl font-bold text-success-400">
          {formatWithCurrency(referralCreditRubles)}
        </div>
        <p className="mt-1 text-sm text-dark-500">{t('earn.invite.referralCreditHint')}</p>
      </div>

      {/* Bot invite link */}
      {botReferralLink ? (
        <div className="bento-card">
          <div className="mb-4 flex items-center gap-2 text-lg font-semibold text-dark-100">
            <TelegramIcon className="h-5 w-5 text-accent-400" />
            {t('earn.invite.botLink')}
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              readOnly
              value={botReferralLink}
              className="input url-ltr flex-1 text-sm"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onCopy(botReferralLink)}
                className={`btn-primary shrink-0 px-4 ${
                  copied ? 'bg-success-500 hover:bg-success-500' : ''
                }`}
              >
                {copied ? <CheckIcon /> : <CopyIcon />}
                <span className="ml-2">
                  {copied ? t('earn.invite.copied') : t('earn.invite.copyLink')}
                </span>
              </button>
              <button
                type="button"
                onClick={shareLink}
                className="btn-secondary flex shrink-0 items-center px-4"
              >
                <ShareIcon className="h-4 w-4" />
                <span className="ml-2">{t('earn.invite.shareButton')}</span>
              </button>
            </div>
          </div>
          <p className="mt-3 text-sm text-dark-500">
            {t('earn.invite.explainer', { percent: commissionPercent })}
          </p>
        </div>
      ) : null}

      {/* Campaigns — invite/referral tools */}
      {campaigns && campaigns.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-500/10 text-accent-400">
              <LinkIcon />
            </div>
            <h2 className="text-lg font-semibold text-dark-100">{t('earn.invite.yourCampaigns')}</h2>
          </div>
          {campaigns.map((campaign) => (
            <CampaignCard key={campaign.id} campaign={campaign} />
          ))}
        </div>
      )}

      {/* Invitees list */}
      <div className="bento-card">
        <h2 className="mb-4 text-lg font-semibold text-dark-100">{t('earn.invite.yourInvitees')}</h2>
        {referralList?.items && referralList.items.length > 0 ? (
          <div className="space-y-3">
            {referralList.items.map((ref) => (
              <div
                key={ref.id}
                className="flex items-center justify-between rounded-xl border border-dark-700/30 bg-dark-800/30 p-3"
              >
                <div>
                  <div className="font-medium text-dark-100">
                    {ref.first_name ||
                      ref.username ||
                      t('earn.invite.anonymousUser', { id: ref.id })}
                  </div>
                  <div className="mt-0.5 text-xs text-dark-500">
                    {formatUserDate(ref.created_at, i18n.language)}
                  </div>
                </div>
                {ref.has_paid ? (
                  <span className="badge-success">{t('earn.invite.status.paid')}</span>
                ) : (
                  <span className="badge-neutral">{t('earn.invite.status.pending')}</span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="py-12 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-800">
              <UsersIcon className="h-8 w-8 text-dark-500" />
            </div>
            <div className="text-dark-400">{t('earn.invite.noInvitees')}</div>
          </div>
        )}
      </div>
    </div>
  );
}
