/** Catalog amounts (price_kopeks) → Toman display unit */
export function catalogKopeksToToman(kopeks: number): number {
  return Math.floor(kopeks / 100);
}

/** balance_kopeks field is stored Toman (Phase B) for fa deploy */
export function canAffordCatalog(balanceToman: number, priceKopeks: number): boolean {
  return balanceToman >= catalogKopeksToToman(priceKopeks);
}

export function missingCatalogToman(balanceToman: number, priceKopeks: number): number {
  return Math.max(0, catalogKopeksToToman(priceKopeks) - balanceToman);
}
