import { PARTNER_STATS } from '../constants/partner';

/** ReferralEarning.amount_kopeks is balance-scale Toman (1:1), not catalog kopeks. */
export function displayReferralEarnings(amountKopeks: number): number {
  return amountKopeks;
}

/** Campaign balance bonuses use catalog kopeks (÷100 for display). */
export function displayCatalogKopeks(kopeks: number): number {
  return kopeks / PARTNER_STATS.KOPEKS_DIVISOR;
}
