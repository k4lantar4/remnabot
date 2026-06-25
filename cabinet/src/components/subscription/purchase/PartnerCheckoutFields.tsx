import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { partnerApi } from '../../../api/partners';

const BRAND_PREFIX_PATTERN = /^[A-Za-z0-9_-]{3,20}$/;
const MAX_PURCHASE_NOTE_LEN = 500;

export interface PartnerCheckoutValues {
  purchaseNote: string;
  panelBrandPrefix: string;
}

interface PartnerCheckoutFieldsProps {
  values: PartnerCheckoutValues;
  onChange: (values: PartnerCheckoutValues) => void;
}

export function PartnerCheckoutFields({ values, onChange }: PartnerCheckoutFieldsProps) {
  const { t } = useTranslation();
  const { data: partnerStatus } = useQuery({
    queryKey: ['partner-status'],
    queryFn: partnerApi.getStatus,
  });

  const isPartner = partnerStatus?.partner_status === 'approved';
  const [brandError, setBrandError] = useState<string | null>(null);
  const [prefilledBrand, setPrefilledBrand] = useState(false);

  useEffect(() => {
    if (prefilledBrand) {
      return;
    }
    const saved = (partnerStatus?.panel_brand_prefix || '').trim();
    if (!saved) {
      return;
    }
    onChange({ purchaseNote: values.purchaseNote, panelBrandPrefix: saved });
    setPrefilledBrand(true);
  }, [partnerStatus?.panel_brand_prefix, prefilledBrand, onChange, values.purchaseNote]);

  if (!isPartner) {
    return null;
  }

  const notePreview = values.purchaseNote.trim()
    ? values.purchaseNote.trim()
    : t('subscription.partner.purchaseNoteEmpty');

  const brandRaw = values.panelBrandPrefix.trim();
  const brandPreview = brandRaw
    ? brandRaw
    : t('subscription.partner.brandPrefixEmpty');

  const handleBrandChange = (next: string) => {
    onChange({ ...values, panelBrandPrefix: next });
    if (!next.trim()) {
      setBrandError(null);
      return;
    }
    setBrandError(
      BRAND_PREFIX_PATTERN.test(next.trim())
        ? null
        : t('subscription.partner.brandPrefixInvalid'),
    );
  };

  return (
    <div className="mb-4 space-y-4 rounded-xl border border-dark-700/50 bg-dark-800/30 p-4">
      <div className="space-y-2">
        <label className="block text-sm font-medium text-dark-200">
          {t('subscription.partner.purchaseNoteLabel')}
        </label>
        <textarea
          value={values.purchaseNote}
          onChange={(e) =>
            onChange({
              ...values,
              purchaseNote: e.target.value.slice(0, MAX_PURCHASE_NOTE_LEN),
            })
          }
          rows={2}
          placeholder={t('subscription.partner.purchaseNotePlaceholder')}
          className="w-full resize-none rounded-lg border border-dark-600 bg-dark-900/50 px-3 py-2 text-sm text-dark-100 placeholder:text-dark-500 focus:border-accent-500 focus:outline-none"
        />
        <p className="text-xs text-dark-400">
          {t('subscription.partner.purchaseNotePreview', { note: notePreview })}
        </p>
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium text-dark-200">
          {t('subscription.partner.brandPrefixLabel')}
        </label>
        <input
          type="text"
          value={values.panelBrandPrefix}
          onChange={(e) => handleBrandChange(e.target.value)}
          placeholder={t('subscription.partner.brandPrefixPlaceholder')}
          className="w-full rounded-lg border border-dark-600 bg-dark-900/50 px-3 py-2 text-sm text-dark-100 placeholder:text-dark-500 focus:border-accent-500 focus:outline-none"
          dir="ltr"
        />
        <p className="text-xs text-dark-500">{t('subscription.partner.brandPrefixHint')}</p>
        {brandError && <p className="text-xs text-error-400">{brandError}</p>}
        <p className="text-xs text-dark-400">
          {t('subscription.partner.brandPrefixPreview', { prefix: brandPreview })}
        </p>
      </div>
    </div>
  );
}

export function isPartnerBrandPrefixValid(prefix: string): boolean {
  const trimmed = prefix.trim();
  return !trimmed || BRAND_PREFIX_PATTERN.test(trimmed);
}
