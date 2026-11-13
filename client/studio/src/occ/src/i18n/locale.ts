// Video Tool: stand-in for OpenChatCut src/i18n/locale.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
// English only (Video Tool's UI is English only). OpenChatCut keys its copy by the Chinese original; the English dictionary is ported as-is.
import { EN } from './dict/en';
import EN_DATA from './dict/en/templates-data';

export type Locale = 'en';
export const ALL_LOCALES: readonly Locale[] = ['en'];
export function getLocale(): Locale { return 'en'; }
export function subscribeLocale(_onChange: () => void): () => void { return () => {}; }
export function localeLanguageName(_locale: Locale = 'en'): 'English' { return 'English'; }
export function setLocale(_next: Locale): void {}
export function prefetchLocaleDicts(): void {}
export function ensureLocaleDict(_locale?: Locale): Promise<void> { return Promise.resolve(); }

/** t('已选 {n}', { n: 3 }): the Chinese original is the key; a missing entry shows the key, as upstream does. */
export function t(zh: string, params?: Record<string, string | number>): string {
  const raw = EN[zh] ?? zh;
  if (!params) return raw;
  return raw.replace(/\{(\w+)\}/g, (match, key: string) => (key in params ? String(params[key]) : match));
}
export function tData(text: string): string {
  return (EN_DATA as Record<string, string>)[text] ?? text;
}
export function localizedCatalogText(zh: string, en?: string): string { return en || t(zh); }
export function useT(): typeof t { return t; }
