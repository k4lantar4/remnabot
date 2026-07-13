export interface CampaignStatsSlice {
  registrations_count: number;
  referrals_count: number;
  earnings_kopeks: number;
}

export interface ReferralInfoFallback {
  total_referrals: number;
  total_earnings_rubles: number;
}

export function aggregatePartnerStats(
  campaigns: CampaignStatsSlice[],
  fallback: ReferralInfoFallback,
) {
  if (campaigns.length === 0) {
    return {
      registrations: 0,
      referrals: fallback.total_referrals,
      earningsKopeks: Math.round(fallback.total_earnings_rubles * 100),
      usedFallback: true,
    };
  }
  return {
    registrations: campaigns.reduce((s, c) => s + (c.registrations_count || 0), 0),
    referrals: campaigns.reduce((s, c) => s + (c.referrals_count || 0), 0),
    earningsKopeks: campaigns.reduce((s, c) => s + (c.earnings_kopeks || 0), 0),
    usedFallback: false,
  };
}
