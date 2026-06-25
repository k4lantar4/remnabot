import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { subscriptionApi } from '../../../api/subscription';
import { getErrorMessage, getInsufficientBalanceError } from '../../../utils/subscriptionHelpers';
import { canAffordCatalog, missingCatalogToman } from '../../../utils/priceUnits';
import { useCurrency } from '../../../hooks/useCurrency';
import InsufficientBalancePrompt from '../../InsufficientBalancePrompt';
import type { Tariff, TariffPeriod } from '../../../types';
import { PackageButton } from './steps/TrafficPlanStep';
import {
  isPartnerBrandPrefixValid,
  PartnerCheckoutFields,
  type PartnerCheckoutValues,
} from './PartnerCheckoutFields';

// ──────────────────────────────────────────────────────────────────
// TariffPurchaseForm
//
// Single-page purchase form: period picker, custom-days toggle,
// custom-traffic toggle + packages/slider, summary, and confirm CTA.
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

  const [selectedTariffPeriod, setSelectedTariffPeriod] = useState<TariffPeriod | null>(
    tariff.periods[0] || null,
  );
  const [customDays, setCustomDays] = useState<number>(30);
  const [customTrafficGb, setCustomTrafficGb] = useState<number>(tariff.min_traffic_gb ?? 1);
  const [useCustomDays, setUseCustomDays] = useState(false);
  const [partnerCheckout, setPartnerCheckout] = useState<PartnerCheckoutValues>({
    purchaseNote: '',
    panelBrandPrefix: '',
  });

  const hasCustomTrafficSection =
    tariff.custom_traffic_enabled === true &&
    ((tariff.traffic_price_per_gb_kopeks ?? 0) > 0 ||
      Object.keys((tariff.traffic_topup_packages as unknown as Record<string, number>) ?? {}).length > 0);

  const isDailyTariff =
    tariff.is_daily || (tariff.daily_price_kopeks && tariff.daily_price_kopeks > 0);
  const periodDays = isDailyTariff
    ? 1
    : useCustomDays
      ? customDays
      : selectedTariffPeriod?.days;
  const quoteTrafficGb = hasCustomTrafficSection ? customTrafficGb : undefined;
  const quoteEnabled =
    !isDailyTariff && periodDays != null && (selectedTariffPeriod != null || useCustomDays);

  const { data: quote } = useQuery({
    queryKey: ['tariff-purchase-quote', tariff.id, periodDays, quoteTrafficGb, subscriptionId],
    queryFn: () =>
      subscriptionApi.getTariffPurchaseQuote(
        tariff.id,
        periodDays!,
        quoteTrafficGb ?? undefined,
        subscriptionId ?? undefined,
      ),
    enabled: quoteEnabled,
  });

  const trafficPackages = quote?.traffic_packages ?? [];

  const perGbKopeks =
    quoteTrafficGb && quoteTrafficGb > 0 && quote?.traffic_kopeks
      ? Math.round(quote.traffic_kopeks / quoteTrafficGb)
      : (tariff.traffic_price_per_gb_kopeks ?? 0);

  const originalTrafficKopeks =
    quote && quote.traffic_kopeks > 0 && quote.discount_percent > 0
      ? Math.round(quote.traffic_kopeks / (1 - quote.discount_percent / 100))
      : (quoteTrafficGb ?? 0) * (tariff.traffic_price_per_gb_kopeks ?? 0);

  const purchaseMutation = useMutation({
    mutationFn: () => {
      const days = periodDays ?? 30;
      const trafficGb = quoteTrafficGb ?? undefined;
      return subscriptionApi.purchaseTariff(
        tariff.id,
        days,
        trafficGb,
        subscriptionId ?? undefined,
        {
          purchaseNote: partnerCheckout.purchaseNote,
          panelBrandPrefix: partnerCheckout.panelBrandPrefix,
        },
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-options'] });
      queryClient.invalidateQueries({ queryKey: ['subscriptions-list'] });
      navigate('/subscriptions', { replace: true });
    },
  });

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

      {isDailyTariff ? (
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

                <PartnerCheckoutFields
                  values={partnerCheckout}
                  onChange={setPartnerCheckout}
                />

                <button
                  onClick={() => purchaseMutation.mutate()}
                  disabled={
                    purchaseMutation.isPending ||
                    !isPartnerBrandPrefixValid(partnerCheckout.panelBrandPrefix)
                  }
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
        <>
          <div>
            <div className="mb-3 text-sm text-dark-400">{t('subscription.selectPeriod')}</div>

            {tariff.periods.length > 0 && !useCustomDays && (
              <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {tariff.periods.map((period) => {
                  const displayPrice = period.price_kopeks;
                  const displayOriginal = period.original_price_kopeks;
                  const displayDiscount = period.discount_percent ?? 0;
                  const displayPerMonth = period.price_per_month_kopeks;

                  return (
                    <button
                      key={period.days}
                      onClick={() => {
                        setSelectedTariffPeriod(period);
                        setUseCustomDays(false);
                      }}
                      className={`relative rounded-xl border p-4 transition-all ${
                        selectedTariffPeriod?.days === period.days && !useCustomDays
                          ? 'border-accent-500 bg-accent-500/10'
                          : 'border-dark-700/50 bg-dark-800/50 hover:border-dark-600'
                      }`}
                    >
                      {displayDiscount > 0 && (
                        <div className="absolute -right-2 -top-2 rounded-full bg-warning-500 px-2 py-0.5 text-xs font-medium text-white">
                          -{displayDiscount}%
                        </div>
                      )}
                      <div className="text-lg font-semibold text-dark-100">{period.label}</div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-accent-400">
                          {formatPrice(displayPrice)}
                        </span>
                        {displayOriginal != null && displayOriginal > displayPrice && (
                          <span className="text-sm text-dark-500 line-through">
                            {formatPrice(displayOriginal)}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-xs text-dark-500">
                        {formatPrice(displayPerMonth)}/{t('subscription.month')}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}

            {tariff.periods.length === 0 &&
              !useCustomDays &&
              !(tariff.custom_days_enabled && (tariff.price_per_day_kopeks ?? 0) > 0) && (
                <div className="rounded-xl border border-warning-500/30 bg-warning-500/10 p-4 text-center">
                  <div className="mb-2 text-sm font-medium text-warning-400">
                    {t('subscription.noPeriodsAvailable')}
                  </div>
                  <div className="text-xs text-dark-400">
                    {t('subscription.noPeriodsAvailableHint')}
                  </div>
                  <button onClick={onBack} className="btn-secondary mt-3 px-4 py-2 text-sm">
                    {t('subscription.chooseDifferentTariff')}
                  </button>
                </div>
              )}

            {tariff.custom_days_enabled && (tariff.price_per_day_kopeks ?? 0) > 0 && (
              <div className="rounded-xl border border-dark-700/50 bg-dark-800/50 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="font-medium text-dark-200">
                    {t('subscription.customDays.title')}
                  </span>
                  <button
                    type="button"
                    onClick={() => setUseCustomDays(!useCustomDays)}
                    role="switch"
                    aria-checked={useCustomDays}
                    aria-label={t('subscription.customDays.title')}
                    className={`relative h-6 w-10 rounded-full transition-colors ${
                      useCustomDays ? 'bg-accent-500' : 'bg-dark-600'
                    }`}
                  >
                    <span
                      className={`absolute top-1 h-4 w-4 rounded-full bg-white transition-transform ${
                        useCustomDays ? 'left-5' : 'left-1'
                      }`}
                    />
                  </button>
                </div>
                {useCustomDays && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min={tariff.min_days ?? 1}
                        max={tariff.max_days ?? 365}
                        value={customDays}
                        onChange={(e) => setCustomDays(parseInt(e.target.value))}
                        className="purchase-range w-full flex-1 accent-accent-500"
                      />
                      <input
                        type="number"
                        value={customDays}
                        min={tariff.min_days ?? 1}
                        max={tariff.max_days ?? 365}
                        onChange={(e) =>
                          setCustomDays(
                            Math.max(
                              tariff.min_days ?? 1,
                              Math.min(
                                tariff.max_days ?? 365,
                                parseInt(e.target.value) || (tariff.min_days ?? 1),
                              ),
                            ),
                          )
                        }
                        className="w-20 rounded-lg border border-dark-600 bg-dark-700 px-3 py-2 text-center text-dark-100"
                      />
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-dark-400">
                        {t('subscription.days', { count: customDays })} ×{' '}
                        {formatPrice(tariff.price_per_day_kopeks ?? 0)}/
                        {t('subscription.customDays.perDay')}
                      </span>
                      {quote && (
                        <span className="font-medium text-accent-400">
                          {formatPrice(quote.period_kopeks + quote.devices_kopeks)}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {hasCustomTrafficSection && (
            <div>
              <div className="rounded-xl border border-dark-700/50 bg-dark-800/50 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium text-dark-200">
                  <svg className="h-4 w-4 text-accent-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
                  </svg>
                  <span>{t('subscription.customTraffic.selectVolume')}</span>
                </div>
                <div className="space-y-4">
                  {trafficPackages.length > 0 && (
                    <div className="grid grid-cols-2 gap-3">
                      {trafficPackages.map((pkg) => (
                        <PackageButton
                          key={pkg.gb}
                          pkg={pkg}
                          selectedTrafficGb={customTrafficGb}
                          onSelectTrafficGb={(gb) => {
                            setCustomTrafficGb(gb);
                          }}
                          formatPrice={formatPrice}
                        />
                      ))}
                    </div>
                  )}
                  {(tariff.traffic_price_per_gb_kopeks ?? 0) > 0 && (
                    <div className="space-y-3">
                      <div className="flex items-center gap-4">
                        <input
                          type="range"
                          min={tariff.min_traffic_gb ?? 1}
                          max={tariff.max_traffic_gb ?? 1000}
                          value={customTrafficGb}
                          onChange={(e) => {
                            setCustomTrafficGb(parseInt(e.target.value));
                          }}
                          className="purchase-range w-full flex-1 accent-accent-500"
                        />
                        <div className="flex items-center gap-2">
                          <input
                            type="number"
                            lang="en"
                            value={customTrafficGb}
                            min={tariff.min_traffic_gb ?? 1}
                            max={tariff.max_traffic_gb ?? 1000}
                            onChange={(e) => {
                              setCustomTrafficGb(
                                Math.max(
                                  tariff.min_traffic_gb ?? 1,
                                  Math.min(
                                    tariff.max_traffic_gb ?? 1000,
                                    parseInt(e.target.value) || (tariff.min_traffic_gb ?? 1),
                                  ),
                                ),
                              );
                            }}
                            className="w-20 rounded-lg border border-dark-600/50 bg-dark-800/50 px-3 py-2 text-center text-dark-100"
                          />
                          <span className="text-dark-400">{t('common.units.gb')}</span>
                        </div>
                      </div>
                      <div className="flex justify-between text-sm text-dark-400">
                        <span>
                          {t('subscription.customTraffic.perGb', 'هر 1 گیگ')}: {formatPrice(perGbKopeks)}
                        </span>
                        <span className="font-medium text-accent-400">
                          +{formatPrice(quote?.traffic_kopeks ?? 0)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {(selectedTariffPeriod || useCustomDays) && (
            <div className="rounded-xl bg-dark-800/50 p-5">
              {quote && (
                <>
                  {quote.discount_percent > 0 && (
                    <div className="mb-3 flex justify-end">
                      <span className="inline-flex items-center gap-1 rounded-full bg-success-500/15 px-2.5 py-0.5 text-xs font-medium text-success-400">
                        تخفیف اعمال شده: {quote.discount_percent}٪
                      </span>
                    </div>
                  )}

                  <div className="mb-4 space-y-3">
                    {(quote.traffic_kopeks ?? 0) > 0 && (
                      <div className="flex items-start justify-between text-sm">
                        <span className="text-dark-300">
                          {t('subscription.summary.traffic', { gb: quoteTrafficGb ?? customTrafficGb })}
                        </span>
                        <div className="flex flex-wrap items-center justify-end gap-x-1.5 gap-y-0.5">
                          {originalTrafficKopeks > quote.traffic_kopeks && (
                            <span className="text-xs text-dark-500 line-through">
                              +{formatPrice(originalTrafficKopeks)}
                            </span>
                          )}
                          <span className="font-medium text-accent-400">
                            +{formatPrice(quote.traffic_kopeks)}
                          </span>
                        </div>
                      </div>
                    )}

                    {useCustomDays ? (
                      <div className="flex justify-between text-sm">
                        <span className="text-dark-300">
                          {t('subscription.stepPeriod')}: {t('subscription.days', { count: customDays })}
                        </span>
                        <span className="font-medium text-dark-200">{formatPrice(quote.period_kopeks + quote.devices_kopeks)}</span>
                      </div>
                    ) : (
                      selectedTariffPeriod && (
                        <>
                          {quote.devices_kopeks > 0 ? (
                            <>
                              <div className="flex items-start justify-between text-sm">
                                <span className="text-dark-300">
                                  {t('subscription.baseTariff')}: {selectedTariffPeriod.label}
                                </span>
                                <div className="flex flex-wrap items-center justify-end gap-x-1.5 gap-y-0.5">
                                  {selectedTariffPeriod.original_price_kopeks &&
                                    selectedTariffPeriod.original_price_kopeks > (selectedTariffPeriod?.price_kopeks ?? quote.period_kopeks) && (
                                      <span className="text-xs text-dark-500 line-through">
                                        {formatPrice(selectedTariffPeriod.original_price_kopeks)}
                                      </span>
                                    )}
                                  <span className={`font-medium ${quote.discount_kopeks > 0 ? 'text-accent-400' : 'text-dark-200'}`}>
                                    {formatPrice(selectedTariffPeriod?.price_kopeks ?? quote.period_kopeks)}
                                  </span>
                                </div>
                              </div>
                              <div className="flex justify-between text-sm text-dark-300">
                                <span>
                                  {t('subscription.extraDevices')} (
                                  {selectedTariffPeriod.extra_devices_count ?? Math.max(0, quote.devices_kopeks)})
                                </span>
                                <span>+{formatPrice(quote.devices_kopeks)}</span>
                              </div>
                            </>
                          ) : (
                            <div className="flex items-start justify-between text-sm">
                              <span className="text-dark-300">
                                {t('subscription.summary.period', { label: selectedTariffPeriod.label })}
                              </span>
                              <div className="flex flex-wrap items-center justify-end gap-x-1.5 gap-y-0.5">
                                {selectedTariffPeriod.original_price_kopeks &&
                                  selectedTariffPeriod.original_price_kopeks >
                                    ((selectedTariffPeriod?.price_kopeks ?? quote.period_kopeks) + quote.devices_kopeks) && (
                                    <span className="text-xs text-dark-500 line-through">
                                      {formatPrice(selectedTariffPeriod.original_price_kopeks)}
                                    </span>
                                  )}
                                <span className={`font-medium ${quote.discount_kopeks > 0 ? 'text-accent-400' : 'text-dark-200'}`}>
                                  {formatPrice((selectedTariffPeriod?.price_kopeks ?? quote.period_kopeks) + quote.devices_kopeks)}
                                </span>
                              </div>
                            </div>
                          )}
                        </>
                      )
                    )}
                  </div>

                  <div className="mb-4 flex items-center justify-between border-t border-dark-700/50 pt-2">
                    <span className="font-medium text-dark-100">{t('subscription.total')}</span>
                    <div className="text-right">
                      <span className="text-2xl font-bold text-accent-400">
                        {formatPrice(quote.final_total)}
                      </span>
                      {quote.discount_kopeks > 0 && (
                        <div className="text-sm text-dark-500 line-through">
                          {formatPrice(quote.original_total)}
                        </div>
                      )}
                    </div>
                  </div>

                  <PartnerCheckoutFields
                    values={partnerCheckout}
                    onChange={setPartnerCheckout}
                  />

                  <button
                    onClick={() => purchaseMutation.mutate()}
                    disabled={
                      purchaseMutation.isPending ||
                      !isPartnerBrandPrefixValid(partnerCheckout.panelBrandPrefix)
                    }
                    className="btn-primary w-full py-3"
                  >
                    {purchaseMutation.isPending ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                        {t('common.loading')}
                      </span>
                    ) : (
                      t('subscription.purchase')
                    )}
                  </button>
                </>
              )}

              {purchaseMutation.isError && !getInsufficientBalanceError(purchaseMutation.error) && (
                <div className="mt-3 text-center text-sm text-error-400">
                  {getErrorMessage(purchaseMutation.error)}
                </div>
              )}
              {purchaseMutation.isError && getInsufficientBalanceError(purchaseMutation.error) && (
                <div className="mt-3">
                  <InsufficientBalancePrompt
                    missingAmountKopeks={
                      getInsufficientBalanceError(purchaseMutation.error)?.missingAmount || 0
                    }
                    missingAmountToman={
                      getInsufficientBalanceError(purchaseMutation.error)?.missingAmount
                    }
                    compact
                  />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
