import { useTranslation } from 'react-i18next'
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '../i18n'

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation()

  const current = (SUPPORTED_LANGUAGES.find((l) => i18n.resolvedLanguage === l) ??
    'zh-TW') as SupportedLanguage

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    void i18n.changeLanguage(e.target.value)
  }

  return (
    <label className="flex items-center gap-1.5 text-xs text-text-muted">
      <span className="sr-only">{t('language.label')}</span>
      <select
        value={current}
        onChange={handleChange}
        aria-label={t('language.label')}
        className="rounded border border-border bg-surface px-2 py-1 text-xs text-text-muted hover:border-accent focus:border-accent focus:outline-none"
      >
        {SUPPORTED_LANGUAGES.map((lng) => (
          <option key={lng} value={lng}>
            {t(`language.${lng}` as const)}
          </option>
        ))}
      </select>
    </label>
  )
}
