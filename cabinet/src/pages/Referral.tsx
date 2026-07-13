import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { referralApi } from '../api/referral';
import { copyToClipboard } from '../utils/clipboard';
import { brandingApi } from '../api/branding';
import { partnerApi } from '../api/partners';
import { EarnTabs, type EarnTabId } from '../components/earn/EarnTabs';
import { InviteTab } from '../components/earn/InviteTab';
import { PartnerTab } from '../components/earn/PartnerTab';
import { useCurrency } from '../hooks/useCurrency';
import { UsersIcon } from '@/components/icons';

export default function Referral() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { formatWithCurrency } = useCurrency();
  const [activeTab, setActiveTab] = useState<EarnTabId>('partner');
  const [copied, setCopied] = useState(false);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  const { data: info, isLoading } = useQuery({
    queryKey: ['referral-info'],
    queryFn: referralApi.getReferralInfo,
  });

  const botReferralLink = info?.bot_referral_link || '';

  const { data: terms } = useQuery({
    queryKey: ['referral-terms'],
    queryFn: referralApi.getReferralTerms,
  });

  const { data: referralList } = useQuery({
    queryKey: ['referral-list'],
    queryFn: () => referralApi.getReferralList({ per_page: 10 }),
  });

  const { data: branding } = useQuery({
    queryKey: ['branding'],
    queryFn: brandingApi.getBranding,
    staleTime: 60000,
  });

  const { data: partnerStatus } = useQuery({
    queryKey: ['partner-status'],
    queryFn: partnerApi.getStatus,
  });

  const isPartner = partnerStatus?.partner_status === 'approved';

  const { data: inventoryStats, isLoading: inventoryLoading } = useQuery({
    queryKey: ['partner-inventory'],
    queryFn: partnerApi.getInventoryStats,
    enabled: isPartner,
    staleTime: 60_000,
  });

  const wholesalePercent = Math.round((partnerStatus?.wholesale_discount_bps ?? 0) / 100);
  const partnerSectionVisible = terms?.partner_section_visible !== false;
  const brandingName = branding?.name || import.meta.env.VITE_APP_NAME || 'Cabinet';

  const copyLink = async (link: string) => {
    if (!link) return;
    try {
      await copyToClipboard(link);
      setCopied(true);
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard write failed silently
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-accent-500 border-t-transparent" />
      </div>
    );
  }

  if (terms && !terms.is_enabled) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6">
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-dark-800">
          <UsersIcon className="h-12 w-12 text-dark-500" />
        </div>
        <div className="text-center">
          <h1 className="mb-2 text-2xl font-bold text-dark-100">{t('earn.title')}</h1>
          <p className="text-dark-400">{t('referral.disabled')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-dark-50 sm:text-3xl">{t('earn.title')}</h1>

      <EarnTabs active={activeTab} onChange={setActiveTab} />

      {activeTab === 'partner' ? (
        <PartnerTab
          partnerSectionVisible={partnerSectionVisible}
          partnerStatus={partnerStatus}
          inventoryStats={inventoryStats}
          inventoryLoading={inventoryLoading}
          wholesalePercent={wholesalePercent}
          onApply={() => navigate('/referral/partner/apply')}
          onBuySubscription={() => navigate('/subscription/purchase')}
          formatAmount={formatWithCurrency}
        />
      ) : (
        <InviteTab
          botReferralLink={botReferralLink}
          referralCreditRubles={info?.available_balance_rubles ?? 0}
          commissionPercent={terms?.commission_percent ?? info?.commission_percent ?? 0}
          brandingName={brandingName}
          referralList={referralList}
          campaigns={isPartner ? partnerStatus?.campaigns : undefined}
          onCopy={copyLink}
          copied={copied}
        />
      )}
    </div>
  );
}
