import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { getGlassColors } from '../../utils/glassTheme';
import { DisableSubscriptionSheet } from './sheets/DisableSubscriptionSheet';
import type { Subscription } from '../../types';

export interface SubscriptionDetailActionsProps {
  subscription: Subscription;
  isMultiTariff: boolean;
  glassColors: ReturnType<typeof getGlassColors>;
  accentHex: string;
  onOpenNote: () => void;
  onToggleAutopay: () => void;
  autopayPending: boolean;
  autopayError?: string | null;
  onOpenTrafficTopup: () => void;
  showTrafficTopup: boolean;
  onRevoke: () => void;
  revokePending: boolean;
  revokeCooldown: number;
  onEnable: () => void;
  enablePending: boolean;
  showDisableSheet: boolean;
  onOpenDisableSheet: () => void;
  onCloseDisableSheet: () => void;
  onDisabled: () => void;
}

function gridButtonStyle(
  g: ReturnType<typeof getGlassColors>,
  accentHex: string,
  active?: boolean,
) {
  return {
    background: active ? `${accentHex}12` : g.innerBg,
    border: active ? `1px solid ${accentHex}30` : `1px solid ${g.innerBorder}`,
    color: active ? accentHex : g.text,
  };
}

const successStyle = {
  background: 'rgba(var(--color-success-400), 0.1)',
  border: '1px solid rgba(var(--color-success-400), 0.28)',
  color: 'rgb(var(--color-success-400))',
};

const warningStyle = {
  background: 'rgba(255,184,0,0.1)',
  border: '1px solid rgba(255,184,0,0.28)',
  color: 'rgb(var(--color-urgent-400))',
};

export function SubscriptionDetailActions({
  subscription,
  isMultiTariff,
  glassColors: g,
  accentHex,
  onOpenNote,
  onToggleAutopay,
  autopayPending,
  autopayError,
  onOpenTrafficTopup,
  showTrafficTopup,
  onRevoke,
  revokePending,
  revokeCooldown,
  onEnable,
  enablePending,
  showDisableSheet,
  onOpenDisableSheet,
  onCloseDisableSheet,
  onDisabled,
}: SubscriptionDetailActionsProps) {
  const { t } = useTranslation();

  if (!isMultiTariff) return null;

  const isExpired =
    !subscription.is_active && !subscription.is_trial && !subscription.is_limited;
  const renewLink = subscription.is_trial
    ? '/subscription/purchase'
    : `/subscriptions/${subscription.id}/renew`;

  const showAutopay =
    subscription.autopay_available === true &&
    !subscription.is_trial &&
    !subscription.is_daily;
  const showDisable =
    (subscription.is_active || subscription.is_limited) &&
    !subscription.user_disabled &&
    !subscription.is_trial;
  const showRenew = !subscription.user_disabled;
  const showDanger =
    (subscription.is_active || subscription.is_limited) && !subscription.is_trial;

  const revokeDisabled = revokePending || revokeCooldown > 0;

  return (
    <div className="space-y-2.5">
      {/* Primary: note + renew */}
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={onOpenNote}
          className="flex items-center justify-center gap-2 rounded-[14px] px-3 py-3.5 text-sm font-semibold transition-colors"
          style={gridButtonStyle(g, accentHex)}
        >
          📝 {t('subscription.noteLabel', 'یادداشت')}
        </button>

        {showRenew && (
          <Link
            to={renewLink}
            className="flex items-center justify-center gap-2 rounded-[14px] px-3 py-3.5 text-sm font-semibold transition-colors"
            style={{
              background: isExpired ? 'rgba(255,59,92,0.08)' : `${accentHex}12`,
              border: isExpired ? '1px solid rgba(255,59,92,0.2)' : `1px solid ${accentHex}30`,
              color: isExpired ? 'rgb(var(--color-critical-500))' : accentHex,
            }}
          >
            {isExpired ? t('subscription.getSubscription') : t('subscription.extend')}
          </Link>
        )}
      </div>

      {/* Traffic topup — green */}
      {showTrafficTopup && (
        <button
          type="button"
          onClick={onOpenTrafficTopup}
          className="flex w-full items-center justify-center gap-2 rounded-[14px] px-3 py-3.5 text-sm font-semibold transition-colors hover:opacity-90"
          style={successStyle}
        >
          + {t('subscription.additionalOptions.buyTraffic')}
        </button>
      )}

      {subscription.user_disabled && (
        <button
          type="button"
          onClick={onEnable}
          disabled={enablePending}
          className="flex w-full items-center justify-center gap-2 rounded-[14px] border border-success-400/30 bg-success-400/10 px-3 py-3.5 text-sm font-semibold text-success-400 transition-colors disabled:opacity-50"
        >
          {enablePending
            ? t('common.processing', 'در حال پردازش...')
            : t('subscription.enable.btn', 'روشن کردن اشتراک')}
        </button>
      )}

      {/* Danger row: reissue link + disable */}
      {showDanger && !subscription.user_disabled && (
        <div className={`grid grid-cols-1 gap-2 ${showDisable ? 'sm:grid-cols-2' : ''}`}>
          <button
            type="button"
            onClick={onRevoke}
            disabled={revokeDisabled}
            className="flex items-center justify-center gap-1.5 rounded-[14px] px-2.5 py-3 text-[12px] font-semibold transition-colors disabled:opacity-50 sm:text-[13px]"
            style={warningStyle}
          >
            {revokePending ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              t('subscription.revoke.button')
            )}
          </button>

          {showDisable && (
            <button
              type="button"
              onClick={onOpenDisableSheet}
              className="flex items-center justify-center gap-1.5 rounded-[14px] border border-error-400/25 bg-error-400/8 px-2.5 py-3 text-[12px] font-semibold text-error-400 transition-colors hover:bg-error-400/12 sm:text-[13px]"
            >
              {t('subscription.disable.btn', 'خاموش کردن')}
            </button>
          )}
        </div>
      )}

      {revokeCooldown > 0 && (
        <p className="text-center text-[11px]" style={{ color: g.textMuted }}>
          {t('subscription.revoke.cooldown', {
            minutes: Math.floor(revokeCooldown / 60),
            seconds: revokeCooldown % 60,
          })}
        </p>
      )}

      {/* Autopay — low priority, full width */}
      {showAutopay && (
        <div className="space-y-1">
          <button
            type="button"
            onClick={onToggleAutopay}
            disabled={autopayPending}
            className="flex w-full items-center justify-center gap-2 rounded-[14px] px-3 py-2.5 text-[12px] font-medium transition-colors disabled:opacity-50"
            style={gridButtonStyle(g, accentHex, subscription.autopay_enabled)}
          >
            <span aria-hidden="true">{subscription.autopay_enabled ? '🟢' : '🔴'}</span>
            {autopayPending
              ? t('common.processing', 'در حال پردازش...')
              : t('subscription.autoRenewal')}
          </button>
          {autopayError && (
            <p className="text-center text-[11px] text-error-400">{autopayError}</p>
          )}
        </div>
      )}

      {showDisableSheet && (
        <DisableSubscriptionSheet
          subscriptionId={subscription.id}
          open={showDisableSheet}
          onOpen={onOpenDisableSheet}
          onClose={onCloseDisableSheet}
          textSecondary={g.textSecondary}
          onDisabled={onDisabled}
          hideDefaultTrigger
        />
      )}
    </div>
  );
}
