import { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { partnerApi } from '../api/partners';
import { AdminBackButton } from '../components/admin';

function bpsToPercent(bps: number): number {
  return bps / 100;
}

function percentToBps(percent: number): number {
  return Math.round(percent * 100);
}

export default function AdminPartnerWholesale() {
  const { t } = useTranslation();
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const passedBps = (location.state as { currentWholesaleBps?: number } | null)?.currentWholesaleBps;

  const { data: partner } = useQuery({
    queryKey: ['admin-partner-detail', userId],
    queryFn: () => partnerApi.getPartnerDetail(Number(userId)),
    enabled: passedBps === undefined && !!userId,
  });

  const currentBps = passedBps ?? partner?.wholesale_discount_bps ?? 0;
  const currentPercent = bpsToPercent(currentBps);
  const [percentValue, setPercentValue] = useState(String(currentPercent));

  useEffect(() => {
    if (partner?.wholesale_discount_bps != null && passedBps === undefined) {
      setPercentValue(String(bpsToPercent(partner.wholesale_discount_bps)));
    }
  }, [partner?.wholesale_discount_bps, passedBps]);

  const updateMutation = useMutation({
    mutationFn: (bps: number) => partnerApi.patchPartnerWholesale(Number(userId), bps),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-partner-detail', userId] });
      queryClient.invalidateQueries({ queryKey: ['admin-partners'] });
      navigate(`/admin/partners/${userId}`);
    },
  });

  const parsedPercent = Number(percentValue);
  const isValid = percentValue !== '' && parsedPercent >= 0 && parsedPercent <= 100;

  return (
    <div className="animate-fade-in">
      <div className="mb-6 flex items-center gap-3">
        <AdminBackButton to={`/admin/partners/${userId}`} />
        <h1 className="text-xl font-semibold text-dark-100">
          {t('admin.partnerDetail.wholesaleDialog.title')}
        </h1>
      </div>

      <div className="rounded-xl border border-dark-700 bg-dark-800 p-6">
        <p className="mb-4 text-sm text-dark-400">
          {t('admin.partnerDetail.wholesaleDialog.description')}
        </p>

        <div className="mb-2 text-sm text-dark-500">
          {t('admin.partnerDetail.wholesale.title')}: {currentPercent}%
        </div>

        <label className="mb-1 block text-sm font-medium text-dark-300">
          {t('admin.partnerDetail.wholesaleDialog.label')}
        </label>
        <input
          type="number"
          min="0"
          max="100"
          step="0.01"
          value={percentValue}
          onChange={(e) => setPercentValue(e.target.value)}
          className="mb-6 w-full rounded-lg border border-dark-600 bg-dark-700 px-3 py-2 text-dark-100 outline-none focus:border-accent-500"
        />

        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/admin/partners/${userId}`)}
            className="flex-1 rounded-lg bg-dark-700 px-4 py-3 text-dark-300 transition-colors hover:bg-dark-600 hover:text-dark-100"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={() => {
              if (isValid) updateMutation.mutate(percentToBps(parsedPercent));
            }}
            disabled={updateMutation.isPending || !isValid}
            className="flex-1 rounded-lg bg-accent-500 px-4 py-3 font-medium text-white transition-colors hover:bg-accent-600 disabled:opacity-50"
          >
            {updateMutation.isPending ? t('common.saving') : t('common.save')}
          </button>
        </div>

        {updateMutation.isError && (
          <div className="mt-4 rounded-lg bg-error-500/10 p-3 text-sm text-error-400">
            {t('common.error')}
          </div>
        )}
      </div>
    </div>
  );
}
