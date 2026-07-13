import { useTranslation } from 'react-i18next';

export type EarnTabId = 'partner' | 'invite';

interface EarnTabsProps {
  active: EarnTabId;
  onChange: (tab: EarnTabId) => void;
}

export function EarnTabs({ active, onChange }: EarnTabsProps) {
  const { t } = useTranslation();
  const tabs: { id: EarnTabId; label: string }[] = [
    { id: 'partner', label: t('earn.tabs.partner') },
    { id: 'invite', label: t('earn.tabs.invite') },
  ];

  return (
    <div className="flex gap-2 rounded-xl bg-dark-800/50 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
            active === tab.id
              ? 'bg-dark-700 text-dark-100'
              : 'text-dark-400 hover:text-dark-200'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
