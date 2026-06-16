import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { subscriptionApi } from '../../../api/subscription';
import { getErrorMessage, getInsufficientBalanceError } from '../../../utils/subscriptionHelpers';
import { canAffordCatalog, missingCatalogToman } from '../../../utils/priceUnits';
import { useCurrency } from '../../../hooks/useCurrency';
import InsufficientBalancePrompt from '../../InsufficientBalancePrompt';
import type { Tariff } from '../../../types';
import { TariffPurchaseWizard } from './TariffPurchaseWizard';

// ──────────────────────────────────────────────────────────────────
// TariffPurchaseForm
//
// The full per-tariff purchase form: period picker (or daily-tariff
// activate), custom-days toggle + slider, custom-traffic toggle +
// slider, summary, and the confirm CTA. Self-owns:
//   - the purchaseTariff mutation
//   - the auto-scroll-into-view ref + effect on mount
//   - selectedTariffPeriod / customDays / customTrafficGb /
//     useCustomDays / useCustomTraffic (form-internal state, reset
//     by re-mount when the parent passes a new `tariff` via key=)
//
// The parent (SubscriptionPurchase) supplies the chosen tariff,
// the current balance (for inline insufficient-balance prompts),
// the subscription id (for the renew-this-subscription flow), and
// onBack to clear its own selection state.
// ──────────────────────────────────────────────────────────────────

export interface TariffPurchaseFormProps {
  tariff: Tariff;
  subscriptionId: number | undefined;
  balanceKopeks: number | undefined;
  onBack: () => void;
}

export function TariffPurchaseForm({
  tariff,
  subscriptionId,
  balanceKopeks,
  onBack,
}: TariffPurchaseFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { formatAmount, currencySymbol } = useCurrency();
  const ref = useRef<HTMLDivElement>(null);

  const formatPrice = (kopeks: number) =>
    kopeks === 0
      ? t('subscription.free', 'Бесплатно')
      : `${formatAmount(kopeks / 100)} ${currencySymbol}`;

  const isDailyTariff = tariff.is_daily || (tariff.daily_price_kopeks && tariff.daily_price_kopeks > 0);

  const purchaseMutation = useMutation({
    mutationFn: () => {
      return subscriptionApi.purchaseTariff(
        tariff.id,
        1,
        undefined,
        subscriptionId ?? undefined,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-options'] });
      queryClient.invalidateQueries({ queryKey: ['subscriptions-list'] });
      navigate('/subscriptions', { replace: true });
    },
  });

  // Smooth scroll the form into view when first mounted.
  useEffect(() => {
    if (ref.current) {
      const timer = setTimeout(() => {
        ref.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, []);

  return (
    <div ref={ref} className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <h3 className="min-w-0 truncate text-lg font-medium text-dark-100">{tariff.name}</h3>
        <button onClick={onBack} className="shrink-0 text-dark-400 hover:text-dark-200">
          ← {t('common.back')}
        </button>
      </div>

      {/* Tariff Info */}
      <div className="rounded-xl bg-dark-800/50 p-4">
        <div className="flex flex-wrap gap-4 text-sm">
          <div>
            <span className="text-dark-500">{t('subscription.traffic')}:</span>
            <span className="ml-2 text-dark-200">{tariff.traffic_limit_label}</span>
          </div>
          <div>
            <span className="text-dark-500">{t('subscription.devices')}:</span>
            <span className="ml-2 text-dark-200">
              {tariff.device_limit === 0 ? '∞' : tariff.device_limit}
              {tariff.extra_devices_count > 0 && (
                <span className="ml-1 text-xs text-accent-400">
                  (+{tariff.extra_devices_count})
                </span>
              )}
            </span>
          </div>
        </div>
      </div>

      {/* Daily Tariff Purchase */}
      {tariff.is_daily || (tariff.daily_price_kopeks && tariff.daily_price_kopeks > 0) ? (
        <div className="rounded-xl border border-accent-500/30 bg-accent-500/10 p-5">
          <div className="mb-4 text-center">
            <div className="mb-2 text-sm text-dark-400">
              {t('subscription.dailyPurchase.costPerDay')}
            </div>
            <div className="text-3xl font-bold text-accent-400">
              {formatPrice(tariff.daily_price_kopeks || 0)}
            </div>
          </div>
          <div className="space-y-2 text-sm text-dark-400">
            <div className="flex items-start gap-2">
              <span className="text-accent-400">•</span>
              <span>{t('subscription.dailyPurchase.chargedDaily')}</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-accent-400">•</span>
              <span>{t('subscription.dailyPurchase.canPause')}</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-accent-400">•</span>
              <span>{t('subscription.dailyPurchase.pausedOnLowBalance')}</span>
            </div>
          </div>

          {(() => {
            const dailyPrice = tariff.daily_price_kopeks || 0;
            const hasEnoughBalance =
              balanceKopeks !== undefined && canAffordCatalog(balanceKopeks, dailyPrice);

            return (
              <div className="mt-6">
                {balanceKopeks !== undefined && !hasEnoughBalance && (
                  <InsufficientBalancePrompt
                    missingAmountKopeks={0}
                    missingAmountToman={missingCatalogToman(balanceKopeks, dailyPrice)}
                    compact
                    className="mb-4"
                  />
                )}

                <button
                  onClick={() => purchaseMutation.mutate()}
                  disabled={purchaseMutation.isPending}
                  className="btn-primary w-full py-3"
                >
                  {purchaseMutation.isPending ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      {t('common.loading')}
                    </span>
                  ) : (
                    t('subscription.dailyPurchase.activate', {
                      price: formatPrice(dailyPrice),
                    })
                  )}
                </button>

                {purchaseMutation.isError &&
                  !getInsufficientBalanceError(purchaseMutation.error) && (
                    <div className="mt-3 text-center text-sm text-error-400">
                      {getErrorMessage(purchaseMutation.error)}
                    </div>
                  )}
                {purchaseMutation.isError &&
                  getInsufficientBalanceError(purchaseMutation.error) && (
                    <div className="mt-3">
                      <InsufficientBalancePrompt
                        missingAmountKopeks={
                          getInsufficientBalanceError(purchaseMutation.error)?.missingAmount || 0
                        }
                        missingAmountToman={
                          getInsufficientBalanceError(purchaseMutation.error)?.missingAmount ||
                          missingCatalogToman(balanceKopeks || 0, dailyPrice)
                        }
                        compact
                      />
                    </div>
                  )}
              </div>
            );
          })()}
        </div>
      ) : (
        <TariffPurchaseWizard
          tariff={tariff}
          subscriptionId={subscriptionId}
          balanceKopeks={balanceKopeks}
        />
      )}
    </div>
  );
}
