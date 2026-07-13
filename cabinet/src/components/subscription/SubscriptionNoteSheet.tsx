import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { subscriptionApi } from '../../api/subscription';
import { Sheet } from '../ui/Sheet';

export interface SubscriptionNoteSheetProps {
  subscriptionId: number;
  purchaseNote?: string | null;
  open: boolean;
  onClose: () => void;
}

export function SubscriptionNoteSheet({
  subscriptionId,
  purchaseNote,
  open,
  onClose,
}: SubscriptionNoteSheetProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(purchaseNote ?? '');

  useEffect(() => {
    if (!open) return;
    setDraft(purchaseNote ?? '');
  }, [open, purchaseNote]);

  const saveMutation = useMutation({
    mutationFn: (note: string | null) => subscriptionApi.updatePurchaseNote(subscriptionId, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription', subscriptionId] });
      queryClient.invalidateQueries({ queryKey: ['subscriptions-list'] });
      onClose();
    },
  });

  const handleSave = () => {
    const trimmed = draft.trim();
    saveMutation.mutate(trimmed ? trimmed : null);
  };

  return (
    <Sheet
      isOpen={open}
      onClose={onClose}
      title={t('subscription.noteLabel', 'یادداشت')}
      snapPoints={[0.72, 1]}
      initialSnap={0}
      contentClassName="px-6 pb-6 pt-5"
    >
      <div className="space-y-3">
        <p className="text-[12px] text-dark-50/35">
          {t('subscription.notePlaceholder', 'یادداشت اختیاری برای این اشتراک')}
        </p>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={500}
          rows={5}
          className="w-full resize-none rounded-2xl border border-dark-700 bg-dark-950/20 px-4 py-3 text-sm text-dark-50 outline-none focus:border-accent-500/40"
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="flex-1 rounded-2xl bg-accent-500 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {saveMutation.isPending
              ? t('common.processing', 'در حال پردازش...')
              : t('subscription.noteSave', 'ذخیره')}
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={saveMutation.isPending}
            className="flex-1 rounded-2xl border border-dark-700 py-3 text-sm font-semibold text-dark-50/70 disabled:opacity-50"
          >
            {t('common.cancel', 'لغو')}
          </button>
        </div>
        <button
          type="button"
          onClick={() => saveMutation.mutate(null)}
          disabled={saveMutation.isPending}
          className="w-full text-center text-xs text-dark-50/45 hover:text-dark-50/65 disabled:opacity-50"
        >
          {t('subscription.noteClear', 'پاک کردن یادداشت')}
        </button>
      </div>
    </Sheet>
  );
}
