import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { QRCodeSVG } from 'qrcode.react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/primitives/Sheet';
import { copyToClipboard } from '@/utils/clipboard';
import { CheckIcon, CopyIcon } from '@/components/icons';

const QR_SCAN_BG = '#b0b0b0';

export interface ConfigDeliverySheetProps {
  open: boolean;
  onClose: () => void;
  configUrl: string | null;
  subscriptionId: number | undefined;
}

export function ConfigDeliverySheet({
  open,
  onClose,
  configUrl,
  subscriptionId,
}: ConfigDeliverySheetProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

  const handleCopy = useCallback(async () => {
    if (!configUrl) return;
    try {
      await copyToClipboard(configUrl);
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard write failed silently
    }
  }, [configUrl]);

  const handleOpenGuide = () => {
    onClose();
    navigate(subscriptionId ? `/connection?sub=${subscriptionId}` : '/connection');
  };

  return (
    <Sheet open={open} onClose={onClose}>
      <SheetContent showCloseButton>
        <SheetHeader className="text-left">
          <SheetTitle>{t('subscription.configDelivery.title')}</SheetTitle>
          <SheetDescription>{t('subscription.configDelivery.subtitle')}</SheetDescription>
        </SheetHeader>

        <div className="mt-4 space-y-4">
          {configUrl ? (
            <>
              <code
                className="block break-all rounded-xl bg-dark-800/60 px-3 py-2 font-mono text-xs text-dark-100"
                title={configUrl}
              >
                {configUrl}
              </code>

              <button
                type="button"
                onClick={handleCopy}
                className={`flex w-full items-center justify-center gap-2 rounded-xl py-3 font-semibold transition-colors ${
                  copied
                    ? 'border border-success-500/40 bg-success-500/15 text-success-400'
                    : 'bg-accent-500 text-white hover:bg-accent-400'
                }`}
              >
                {copied ? <CheckIcon className="h-5 w-5" /> : <CopyIcon className="h-5 w-5" />}
                {copied
                  ? t('subscription.configDelivery.copied')
                  : t('subscription.configDelivery.copyConfig')}
              </button>

              <div className="qr-scan-frame flex flex-col items-center rounded-2xl p-4">
                <div className="qr-scan-surface rounded-xl p-3">
                  <QRCodeSVG
                    value={configUrl}
                    size={200}
                    level="M"
                    includeMargin={false}
                    bgColor={QR_SCAN_BG}
                    fgColor="#000000"
                  />
                </div>
                <p className="mt-3 text-center text-xs text-dark-400">
                  {t('subscription.configDelivery.qrHint')}
                </p>
              </div>
            </>
          ) : (
            <p className="text-sm text-dark-400">{t('subscription.connection.noSubscription')}</p>
          )}

          <button
            type="button"
            onClick={handleOpenGuide}
            className="w-full rounded-xl bg-accent-500 py-3 font-semibold text-white transition-colors hover:bg-accent-400"
          >
            {t('subscription.configDelivery.openGuide')}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
