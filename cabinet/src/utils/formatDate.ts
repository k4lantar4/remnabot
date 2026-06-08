const LOCALE_MAP: Record<string, string> = {
  ru: 'ru-RU',
  en: 'en-US',
  zh: 'zh-CN',
  fa: 'fa-IR',
};

function resolveLocale(lang?: string): string | undefined {
  if (!lang) return undefined;
  const code = lang.split('-')[0].toLowerCase();
  return LOCALE_MAP[code] ?? lang;
}

function isJalaliLanguage(lang?: string): boolean {
  return (lang ?? '').split('-')[0].toLowerCase() === 'fa';
}

export function formatUserDate(
  iso: string | null | undefined,
  lang?: string,
  options: Intl.DateTimeFormatOptions = {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  },
): string {
  if (!iso) return '—';
  try {
    const normalized = iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`;
    const date = new Date(normalized);
    if (Number.isNaN(date.getTime())) return '—';

    const locale = resolveLocale(lang);
    const jalali = isJalaliLanguage(lang);

    return date.toLocaleDateString(locale, jalali ? { ...options, calendar: 'persian' } : options);
  } catch {
    return '—';
  }
}

export function formatUserDateTime(
  iso: string | null | undefined,
  lang?: string,
): string {
  return formatUserDate(iso, lang, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
