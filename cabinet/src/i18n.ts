import i18n, { type ResourceLanguage } from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

const localeLoaders: Record<string, () => Promise<{ default: ResourceLanguage }>> = {
  ru: () => import('./locales/ru.json'),
  en: () => import('./locales/en.json'),
  zh: () => import('./locales/zh.json'),
  fa: () => import('./locales/fa.json'),
};

const SUPPORTED_LANGS = Object.keys(localeLoaders);
/** Deployment default — matches bot ``DEFAULT_LANGUAGE`` (fa). */
const DEFAULT_LNG = 'fa';
/** Secondary bundle for missing fa keys. */
const FALLBACK_LNG = 'ru';
const LANGUAGE_STORAGE_KEY = 'cabinet_language';

const loadedLanguages = new Set<string>();

async function loadLanguage(lng: string): Promise<void> {
  if (loadedLanguages.has(lng)) return;

  const loader = localeLoaders[lng];
  if (!loader) return;

  const mod = await loader();
  i18n.addResourceBundle(lng, 'translation', mod.default, true, true);
  loadedLanguages.add(lng);
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    lng: DEFAULT_LNG,
    fallbackLng: [DEFAULT_LNG, FALLBACK_LNG, 'en'],
    supportedLngs: SUPPORTED_LANGS,
    partialBundledLanguages: true,

    detection: {
      // Only explicit LanguageSwitcher choice — not browser navigator (often en).
      order: ['localStorage'],
      caches: ['localStorage'],
      lookupLocalStorage: 'cabinet_language',
    },

    interpolation: {
      escapeValue: false,
    },

    react: {
      useSuspense: false,
    },

    showSupportNotice: false,
  });

// Load default language + fallback on startup
const detectedLng = i18n.language?.split('-')[0] || DEFAULT_LNG;
const langsToLoad = [DEFAULT_LNG, FALLBACK_LNG, ...(detectedLng !== DEFAULT_LNG && detectedLng !== FALLBACK_LNG ? [detectedLng] : [])];
Promise.all(langsToLoad.map(loadLanguage));

// Keep <html lang> + dir in sync with i18n so screen readers pronounce
// content correctly, browsers don't offer to translate it, and RTL
// languages (fa) flip layout direction. index.html ships with lang="fa"
// for the first paint; runtime updates take over from there.
const RTL_LANGS = new Set(['fa', 'ar', 'he', 'ur']);
function syncHtmlLang(lng: string): void {
  const code = lng.split('-')[0];
  if (typeof document === 'undefined') return;
  if (document.documentElement.lang !== code) {
    document.documentElement.lang = code;
  }
  const dir = RTL_LANGS.has(code) ? 'rtl' : 'ltr';
  if (document.documentElement.dir !== dir) {
    document.documentElement.dir = dir;
  }
}
syncHtmlLang(detectedLng);

// Lazy-load on language change
i18n.on('languageChanged', (lng: string) => {
  const code = lng.split('-')[0];
  loadLanguage(code);
  syncHtmlLang(code);
});

/**
 * Apply cabinet UI language when the user has not made an explicit choice
 * (no ``cabinet_language`` in localStorage). Prefers the authenticated user's
 * stored language; otherwise ``DEFAULT_LNG`` (fa).
 */
export function applyCabinetLanguagePreference(preferred?: string | null): void {
  try {
    if (localStorage.getItem(LANGUAGE_STORAGE_KEY)) return;
  } catch {
    return;
  }
  const raw = preferred?.split('-')[0]?.toLowerCase();
  const code = raw && SUPPORTED_LANGS.includes(raw) ? raw : DEFAULT_LNG;
  if (i18n.language?.split('-')[0] !== code) {
    i18n.changeLanguage(code);
  }
}

/** @deprecated Use applyCabinetLanguagePreference — Telegram client lang is not auto-applied. */
export function applyTelegramLanguage(): void {
  applyCabinetLanguagePreference();
}

export default i18n;
