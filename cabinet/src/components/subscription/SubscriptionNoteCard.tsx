import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { subscriptionApi } from '../../api/subscription';

export interface SubscriptionNoteCardProps {
  subscriptionId: number;
  purchaseNote?: string | null;
  textSecondary: string;
  innerBg: string;
  innerBorder: string;
}

export function SubscriptionNoteCard({
  subscriptionId,
  purchaseNote,
  textSecondary,
  innerBg,
  innerBorder,
}: SubscriptionNoteCardProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(purchaseNote ?? '');

  useEffect(() => {
    if (!isEditing) {
      setDraft(purchaseNote ?? '');
    }
  }, [purchaseNote, isEditing]);

  const saveMutation = useMutation({
    mutationFn: (note: string | null) => subscriptionApi.updatePurchaseNote(subscriptionId, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription', subscriptionId] });
      queryClient.invalidateQueries({ queryKey: ['subscriptions-list'] });
      setIsEditing(false);
    },
  });

  const handleSave = () => {
    const trimmed = draft.trim();
    saveMutation.mutate(trimmed ? trimmed : null);
  };

  return (
    <div
      className="rounded-2xl p-4"
      style={{ background: innerBg, border: `1px solid ${innerBorder}` }}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-dark-50">
          {t('subscription.noteLabel', 'یادداشت')}
        </span>
        {!isEditing && (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="rounded-lg border border-accent-500/30 bg-accent-500/10 px-3 py-1.5 text-xs font-semibold text-accent-400 transition-colors hover:bg-accent-500/20"
          >
            {t('subscription.noteEdit', 'ویرایش')}
          </button>
        )}
      </div>

      {isEditing ? (
        <div className="space-y-3">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={500}
            rows={3}
            placeholder={t('subscription.notePlaceholder', 'یادداشت اختیاری برای این اشتراک')}
            className="w-full resize-none rounded-xl border border-dark-700 bg-dark-900/60 px-3 py-2 text-sm text-dark-50 outline-none focus:border-accent-500/50"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saveMutation.isPending}
              className="flex-1 rounded-xl bg-accent-500 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {saveMutation.isPending
                ? t('common.processing', 'در حال پردازش...')
                : t('subscription.noteSave', 'ذخیره')}
            </button>
            <button
              type="button"
              onClick={() => {
                setDraft(purchaseNote ?? '');
                setIsEditing(false);
              }}
              disabled={saveMutation.isPending}
              className="flex-1 rounded-xl border border-dark-700 py-2 text-sm font-medium text-dark-50/80"
            >
              {t('common.cancel', 'لغو')}
            </button>
          </div>
          <button
            type="button"
            onClick={() => saveMutation.mutate(null)}
            disabled={saveMutation.isPending}
            className="text-xs text-dark-50/50 hover:text-dark-50/70"
          >
            {t('subscription.noteClear', 'پاک کردن یادداشت')}
          </button>
        </div>
      ) : (
        <p className="text-sm" style={{ color: purchaseNote ? undefined : textSecondary }}>
          {purchaseNote?.trim()
            ? purchaseNote
            : t('subscription.notePlaceholder', 'یادداشت اختیاری برای این اشتراک')}
        </p>
      )}
    </div>
  );
}
