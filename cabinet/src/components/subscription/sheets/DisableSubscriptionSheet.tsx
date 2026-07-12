import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { subscriptionApi } from '../../../api/subscription';
import { usePlatform } from '../../../platform';
import { useDestructiveConfirm } from '../../../platform/hooks/useNativeDialog';

export interface DisableSubscriptionSheetProps {
  subscriptionId: number;
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  onDisabled: () => void;
  textSecondary: string;
}

export function DisableSubscriptionSheet({
  subscriptionId,
  open,
  onOpen,
  onClose,
  onDisabled,
  textSecondary,
}: DisableSubscriptionSheetProps) {
  const { t } = useTranslation();
  const { platform } = usePlatform();
  const destructiveConfirm = useDestructiveConfirm();
  const [loading, setLoading] = useState(false);

  const performDisable = async () => {
    setLoading(true);
    try {
      await subscriptionApi.disableSubscription(subscriptionId);
      onDisabled();
    } catch {
      setLoading(false);
      onClose();
    }
  };

  const handleTriggerClick = async () => {
    if (platform === 'telegram') {
      const confirmed = await destructiveConfirm(
        t(
          'subscription.disable.warning',
          'دسترسی VPN قطع می‌شود. هر زمان با دکمهٔ روشن کردن می‌توانید دوباره فعال کنید — بدون نیاز به تمدید.',
        ),
        t('subscription.disable.confirmBtn', 'بله، خاموش کن'),
        t('subscription.disable.title', 'خاموش کردن اشتراک؟'),
      );
      if (!confirmed) return;
      await performDisable();
    } else {
      onOpen();
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={handleTriggerClick}
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-2xl border border-error-400/20 bg-error-400/5 p-3.5 text-sm font-medium text-error-400 transition-colors hover:bg-error-400/10 disabled:opacity-50"
      >
        {t('subscription.disable.btn', 'خاموش کردن اشتراک')}
      </button>
    );
  }

  return (
    <div
      className="rounded-2xl border border-error-400/20 p-4"
      style={{ background: 'rgba(255,59,92,0.04)' }}
    >
      <div className="mb-3 text-sm font-semibold text-error-400">
        {t('subscription.disable.title', 'خاموش کردن اشتراک؟')}
      </div>
      <div className="mb-4 text-xs" style={{ color: textSecondary }}>
        {t(
          'subscription.disable.warning',
          'دسترسی VPN قطع می‌شود. هر زمان با دکمهٔ روشن کردن می‌توانید دوباره فعال کنید — بدون نیاز به تمدید.',
        )}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={performDisable}
          disabled={loading}
          className="flex-1 rounded-xl bg-error-500 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-error-600 disabled:opacity-50"
        >
          {loading
            ? t('common.processing', 'در حال پردازش...')
            : t('subscription.disable.confirmBtn', 'بله، خاموش کن')}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="flex-1 rounded-xl border border-dark-700 py-2.5 text-sm font-medium transition-colors hover:bg-dark-700"
          style={{ color: textSecondary }}
        >
          {t('common.cancel', 'لغو')}
        </button>
      </div>
    </div>
  );
}
