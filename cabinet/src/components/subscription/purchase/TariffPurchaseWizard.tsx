import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { subscriptionApi } from '../../../api/subscription';
import { useCurrency } from '../../../hooks/useCurrency';
import InsufficientBalancePrompt from '../../InsufficientBalancePrompt';
import { getErrorMessage, getInsufficientBalanceError } from '../../../utils/subscriptionHelpers';
import type { Tariff } from '../../../types';
import { ConfirmStep } from './steps/ConfirmStep';
import { PeriodStep } from './steps/PeriodStep';
import { TrafficPlanStep } from './steps/TrafficPlanStep';

type WizardStep = 'traffic' | 'period' | 'confirm';

interface TariffPurchaseWizardProps {
  tariff: Tariff;
  subscriptionId: number | undefined;
  balanceKopeks: number | undefined;
}

export function TariffPurchaseWizard({
  tariff,
  subscriptionId,
  balanceKopeks,
}: TariffPurchaseWizardProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { formatAmount, currencySymbol } = useCurrency();

  const formatPrice = (kopeks: number) =>
    kopeks === 0
      ? t('subscription.free', 'Бесплатно')
      : `${formatAmount(kopeks / 100)} ${currencySymbol}`;

  const [step, setStep] = useState<WizardStep>('traffic');
  const [selectedTrafficGb, setSelectedTrafficGb] = useState<number>(tariff.min_traffic_gb ?? tariff.traffic_limit_gb);
  const [selectedPeriodDays, setSelectedPeriodDays] = useState<number | null>(tariff.periods[0]?.days ?? null);

  const { data: baseQuote } = useQuery({
    queryKey: ['tariff-purchase-quote-base', tariff.id, subscriptionId],
    queryFn: () => subscriptionApi.getTariffPurchaseQuote(tariff.id, undefined, undefined, subscriptionId),
    enabled: !!tariff.id,
  });

  const { data: quote, isLoading: quoteLoading } = useQuery({
    queryKey: ['tariff-purchase-quote-split', tariff.id, selectedPeriodDays, selectedTrafficGb, subscriptionId],
    queryFn: () =>
      subscriptionApi.getTariffPurchaseQuote(
        tariff.id,
        selectedPeriodDays ?? undefined,
        selectedTrafficGb,
        subscriptionId,
      ),
    enabled: selectedPeriodDays != null,
  });

  const purchaseMutation = useMutation({
    mutationFn: () =>
      subscriptionApi.purchaseTariff(
        tariff.id,
        selectedPeriodDays ?? tariff.periods[0]?.days ?? 30,
        selectedTrafficGb,
        subscriptionId ?? undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription'] });
      queryClient.invalidateQueries({ queryKey: ['purchase-options'] });
      queryClient.invalidateQueries({ queryKey: ['subscriptions-list'] });
      navigate('/subscriptions', { replace: true });
    },
  });

  const trafficPackages = useMemo(() => {
    return (baseQuote?.traffic_packages ?? []).map((pkg) => ({
      gb: pkg.gb,
      price_kopeks: pkg.price_kopeks,
      original_price_kopeks: pkg.original_price_kopeks,
      discount_percent: pkg.discount_percent,
      label: pkg.label,
    }));
  }, [baseQuote]);

  const selectedPeriodLabel =
    tariff.periods.find((period) => period.days === selectedPeriodDays)?.label ??
    t('subscription.days', { count: selectedPeriodDays ?? 0 });

  const handleSelectTrafficGb = (gb: number) => {
    setSelectedTrafficGb(gb);
    setStep('period');
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        {(['traffic', 'period', 'confirm'] as WizardStep[]).map((item, idx) => (
          <div
            key={item}
            className={`h-1 flex-1 rounded-full ${
              ['traffic', 'period', 'confirm'].indexOf(step) >= idx ? 'bg-accent-500' : 'bg-dark-700'
            }`}
          />
        ))}
      </div>

      {step === 'traffic' && (
        <TrafficPlanStep
          selectedTrafficGb={selectedTrafficGb}
          minTrafficGb={tariff.min_traffic_gb ?? 1}
          maxTrafficGb={tariff.max_traffic_gb ?? 1000}
          packages={trafficPackages}
          onSelectTrafficGb={handleSelectTrafficGb}
          onComplete={() => setStep('period')}
          formatPrice={formatPrice}
        />
      )}

      {step === 'period' && (
        <PeriodStep
          periods={tariff.periods}
          selectedPeriodDays={selectedPeriodDays}
          selectedTrafficGb={selectedTrafficGb}
          trafficSubtotalKopeks={quote?.traffic_kopeks ?? 0}
          runningTotalKopeks={quote?.final_total ?? 0}
          onSelectPeriodDays={setSelectedPeriodDays}
          formatPrice={formatPrice}
        />
      )}

      {step === 'confirm' && quote && (
        <ConfirmStep
          periodLabel={selectedPeriodLabel}
          trafficGb={selectedTrafficGb}
          periodKopeks={quote.period_kopeks}
          trafficKopeks={quote.traffic_kopeks}
          finalTotalKopeks={quote.final_total}
          discountKopeks={quote.discount_kopeks}
          originalTotalKopeks={quote.original_total}
          formatPrice={formatPrice}
        />
      )}

      {step === 'confirm' && quoteLoading && (
        <div className="py-4 text-center text-sm text-dark-400">{t('common.loading')}</div>
      )}

      {step === 'confirm' && purchaseMutation.isError && getInsufficientBalanceError(purchaseMutation.error) && (
        <InsufficientBalancePrompt
          missingAmountKopeks={getInsufficientBalanceError(purchaseMutation.error)?.missingAmount || 0}
          missingAmountToman={getInsufficientBalanceError(purchaseMutation.error)?.missingAmount}
          compact
        />
      )}
      {step === 'confirm' &&
        purchaseMutation.isError &&
        !getInsufficientBalanceError(purchaseMutation.error) && (
          <div className="text-center text-sm text-error-400">{getErrorMessage(purchaseMutation.error)}</div>
        )}

      {step === 'confirm' && balanceKopeks != null && quote && balanceKopeks < quote.final_total / 100 && (
        <InsufficientBalancePrompt
          missingAmountKopeks={Math.max(0, quote.final_total - balanceKopeks * 100)}
          missingAmountToman={Math.max(0, Math.ceil(quote.final_total / 100) - balanceKopeks)}
          compact
        />
      )}

      {step !== 'traffic' && (
        <div className="flex gap-2 border-t border-dark-700/50 pt-4">
          <button
            onClick={() => setStep(step === 'confirm' ? 'period' : 'traffic')}
            className="btn-secondary flex-1"
          >
            {t('common.back')}
          </button>

          {step === 'period' ? (
            <button
              onClick={() => setStep('confirm')}
              disabled={selectedPeriodDays == null}
              className="btn-primary flex-1"
            >
              {t('common.next')}
            </button>
          ) : (
            <button onClick={() => purchaseMutation.mutate()} disabled={purchaseMutation.isPending} className="btn-primary flex-1">
              {purchaseMutation.isPending ? t('common.loading') : t('subscription.purchase')}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
