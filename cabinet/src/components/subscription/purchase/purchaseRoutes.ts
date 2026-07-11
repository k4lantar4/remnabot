/** Catalog purchase without binding to an existing subscription (multi-tariff buyAnother). */
export const NEW_PURCHASE_PATH = '/subscription/purchase?intent=new';

export function isNewPurchaseIntent(searchParams: URLSearchParams): boolean {
  return searchParams.get('intent') === 'new';
}
