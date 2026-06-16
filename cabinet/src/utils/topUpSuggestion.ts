/** Round missing balance up to the nearest 1000 Toman (matches bot topup_suggestion). */
export function suggestTopUpAmount(displayMissing: number): number {
  if (displayMissing <= 0) return 0;
  return Math.ceil(displayMissing / 1000) * 1000;
}
