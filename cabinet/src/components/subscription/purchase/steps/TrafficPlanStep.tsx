import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

export interface TrafficPackageOption {
  gb: number;
  price_kopeks: number;
  label?: string;
}

interface TrafficPlanStepProps {
  selectedTrafficGb: number;
  minTrafficGb: number;
  maxTrafficGb: number;
  packages: TrafficPackageOption[];
  onSelectTrafficGb: (gb: number) => void;
  formatPrice: (kopeks: number) => string;
}

export function TrafficPlanStep({
  selectedTrafficGb,
  minTrafficGb,
  maxTrafficGb,
  packages,
  onSelectTrafficGb,
  formatPrice,
}: TrafficPlanStepProps) {
  const { t } = useTranslation();
  const [customOpen, setCustomOpen] = useState(false);
  const [customValue, setCustomValue] = useState(String(selectedTrafficGb));

  const hasSelectedPackage = useMemo(
    () => packages.some((pkg) => pkg.gb === selectedTrafficGb),
    [packages, selectedTrafficGb],
  );

  const applyCustomTraffic = () => {
    const parsed = Number.parseInt(customValue, 10);
    if (Number.isNaN(parsed)) {
      return;
    }
    const bounded = Math.max(minTrafficGb, Math.min(maxTrafficGb, parsed));
    onSelectTrafficGb(bounded);
    setCustomValue(String(bounded));
    setCustomOpen(false);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-dark-700/50 bg-dark-800/50 p-4">
        <div className="text-sm text-dark-400">
          {t('subscription.customTraffic.selectVolume', 'Select traffic volume')}
        </div>
        <div className="mt-1 text-lg font-semibold text-dark-100">
          {selectedTrafficGb} {t('common.units.gb')}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {packages.map((pkg) => (
          <button
            key={pkg.gb}
            onClick={() => onSelectTrafficGb(pkg.gb)}
            className={`rounded-xl border p-4 text-left transition-all ${
              selectedTrafficGb === pkg.gb
                ? 'border-accent-500 bg-accent-500/10'
                : 'border-dark-700/50 bg-dark-800/50 hover:border-dark-600'
            }`}
          >
            <div className="text-base font-semibold text-dark-100">{pkg.gb} GB</div>
            <div className="mt-1 text-sm text-accent-400">{formatPrice(pkg.price_kopeks)}</div>
          </button>
        ))}
      </div>

      <button
        onClick={() => setCustomOpen(true)}
        className={`btn-secondary w-full ${hasSelectedPackage ? '' : 'border-accent-500/40 text-accent-400'}`}
      >
        {t('subscription.customTraffic.customVolume', 'حجم دلخواه')}
      </button>

      {customOpen && (
        <div className="rounded-xl border border-dark-700/50 bg-dark-800/70 p-4">
          <div className="mb-2 text-sm text-dark-300">
            {t('subscription.customTraffic.inputRange', 'Enter GB between {{min}} and {{max}}', {
              min: minTrafficGb,
              max: maxTrafficGb,
            })}
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={customValue}
              min={minTrafficGb}
              max={maxTrafficGb}
              onChange={(e) => setCustomValue(e.target.value)}
              className="w-full rounded-lg border border-dark-600 bg-dark-700 px-3 py-2 text-dark-100"
            />
            <span className="text-dark-400">{t('common.units.gb')}</span>
          </div>
          <div className="mt-3 flex gap-2">
            <button onClick={applyCustomTraffic} className="btn-primary flex-1">
              {t('common.apply', 'Apply')}
            </button>
            <button onClick={() => setCustomOpen(false)} className="btn-secondary flex-1">
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
