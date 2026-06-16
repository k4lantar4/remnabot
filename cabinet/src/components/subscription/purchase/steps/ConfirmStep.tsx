import { useTranslation } from 'react-i18next';

interface ConfirmStepProps {
  periodLabel: string;
  trafficGb: number;
  periodKopeks: number;
  trafficKopeks: number;
  finalTotalKopeks: number;
  discountKopeks: number;
  originalTotalKopeks: number;
  formatPrice: (kopeks: number) => string;
}

export function ConfirmStep({
  periodLabel,
  trafficGb,
  periodKopeks,
  trafficKopeks,
  finalTotalKopeks,
  discountKopeks,
  originalTotalKopeks,
  formatPrice,
}: ConfirmStepProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-3 rounded-xl bg-dark-800/50 p-5">
      <div className="flex justify-between text-sm text-dark-300">
        <span>{t('subscription.stepPeriod')}: {periodLabel}</span>
        <span>{formatPrice(periodKopeks)}</span>
      </div>
      <div className="flex justify-between text-sm text-dark-300">
        <span>{t('subscription.summary.traffic', { gb: trafficGb })}</span>
        <span>+{formatPrice(trafficKopeks)}</span>
      </div>
      {discountKopeks > 0 && (
        <div className="flex justify-between text-sm text-success-400">
          <span>{t('promo.discountApplied')}</span>
          <span>-{formatPrice(discountKopeks)}</span>
        </div>
      )}
      <div className="flex items-center justify-between border-t border-dark-700/50 pt-3">
        <span className="font-medium text-dark-100">{t('subscription.total')}</span>
        <div className="text-right">
          <div className="text-2xl font-bold text-accent-400">{formatPrice(finalTotalKopeks)}</div>
          {originalTotalKopeks > finalTotalKopeks && (
            <div className="text-xs text-dark-500 line-through">{formatPrice(originalTotalKopeks)}</div>
          )}
        </div>
      </div>
    </div>
  );
}
