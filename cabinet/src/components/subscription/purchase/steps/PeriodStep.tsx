import { useTranslation } from 'react-i18next';
import type { TariffPeriod } from '../../../../types';

interface PeriodStepProps {
  periods: TariffPeriod[];
  selectedPeriodDays: number | null;
  selectedTrafficGb: number;
  trafficSubtotalKopeks: number;
  runningTotalKopeks: number;
  onSelectPeriodDays: (days: number) => void;
  formatPrice: (kopeks: number) => string;
}

export function PeriodStep({
  periods,
  selectedPeriodDays,
  selectedTrafficGb,
  trafficSubtotalKopeks,
  runningTotalKopeks,
  onSelectPeriodDays,
  formatPrice,
}: PeriodStepProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {periods.map((period) => (
          <button
            key={period.days}
            onClick={() => onSelectPeriodDays(period.days)}
            className={`rounded-xl border p-4 text-left transition-all ${
              selectedPeriodDays === period.days
                ? 'border-accent-500 bg-accent-500/10'
                : 'border-dark-700/50 bg-dark-800/50 hover:border-dark-600'
            }`}
          >
            <div className="text-base font-semibold text-dark-100">{period.label}</div>
            <div className="mt-1 text-sm text-accent-400">{formatPrice(period.price_kopeks)}</div>
            <div className="mt-1 text-xs text-dark-500">
              {t('subscription.periodOnlyPrice', 'Period-only price')}
            </div>
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-dark-700/50 bg-dark-800/50 p-4 text-sm">
        <div className="flex justify-between text-dark-300">
          <span>
            {t('subscription.summary.traffic', { gb: selectedTrafficGb })}
          </span>
          <span>+{formatPrice(trafficSubtotalKopeks)}</span>
        </div>
        <div className="mt-2 flex justify-between border-t border-dark-700/50 pt-2 font-medium text-dark-100">
          <span>{t('subscription.runningTotal', 'Running total')}</span>
          <span>{formatPrice(runningTotalKopeks)}</span>
        </div>
      </div>
    </div>
  );
}
