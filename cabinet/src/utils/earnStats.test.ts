import { describe, it, expect } from 'vitest';
import { aggregatePartnerStats } from './earnStats';

describe('aggregatePartnerStats', () => {
  it('sums campaign counters', () => {
    const result = aggregatePartnerStats(
      [
        { registrations_count: 10, referrals_count: 3, earnings_kopeks: 50000 },
        { registrations_count: 5, referrals_count: 2, earnings_kopeks: 25000 },
      ],
      { total_referrals: 99, total_earnings_rubles: 999 },
    );
    expect(result).toEqual({
      registrations: 15,
      referrals: 5,
      earningsKopeks: 75000,
      usedFallback: false,
    });
  });

  it('falls back to referral info when no campaigns', () => {
    const result = aggregatePartnerStats([], {
      total_referrals: 4,
      total_earnings_rubles: 12000,
    });
    expect(result).toEqual({
      registrations: 0,
      referrals: 4,
      earningsKopeks: 1200000,
      usedFallback: true,
    });
  });
});
