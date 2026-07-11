/** Post-purchase navigation target: subscription detail with config sheet auto-open. */
export function getPostPurchasePath(subscriptionId: number): string {
  return `/subscriptions/${subscriptionId}?openConfig=1`;
}
