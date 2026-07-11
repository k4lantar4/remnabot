import { describe, expect, it } from 'vitest';
import { getPostPurchasePath } from './postPurchaseRedirect';

describe('getPostPurchasePath', () => {
  it('returns subscription detail with openConfig query', () => {
    expect(getPostPurchasePath(42)).toBe('/subscriptions/42?openConfig=1');
  });
});
