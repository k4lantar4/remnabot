import { useCallback } from 'react';
import { useCurrency } from '@/hooks/useCurrency';
import { catalogKopeksToToman } from '@/utils/priceUnits';

/** Catalog price_kopeks → display amount with locale-aware currency symbol. */
export function useCatalogKopeksDisplay() {
  const { formatAmount, currencySymbol } = useCurrency();

  const formatCatalogKopeks = useCallback(
    (kopeks: number) => `${formatAmount(catalogKopeksToToman(kopeks))} ${currencySymbol}`,
    [formatAmount, currencySymbol],
  );

  return { formatCatalogKopeks, currencySymbol };
}
