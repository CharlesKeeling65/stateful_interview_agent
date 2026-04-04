import type { Locale } from '../i18n'

const DISPLAY_TIME_ZONE = 'Asia/Shanghai'

export function parseApiDate(value: string) {
  const normalizedValue =
    /z|[+-]\d{2}:\d{2}$/i.test(value) ? value : `${value}Z`
  return new Date(normalizedValue)
}

export function parseApiDateMs(value: string) {
  return parseApiDate(value).getTime()
}

export function formatTimestamp(value: string, locale: Locale = 'en') {
  return new Intl.DateTimeFormat(locale === 'zh-CN' ? 'zh-CN' : 'en-US', {
    month: locale === 'zh-CN' ? 'long' : 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: DISPLAY_TIME_ZONE,
    timeZoneName: locale === 'zh-CN' ? undefined : 'short',
  }).format(parseApiDate(value))
}

export function formatDurationMs(value: number | null | undefined, locale: Locale = 'en') {
  if (!value || value <= 0) {
    return locale === 'zh-CN' ? '0秒' : '0s'
  }

  if (value < 1000) {
    return `${value}ms`
  }

  const totalSeconds = value / 1000
  if (totalSeconds < 60) {
    const renderedSeconds = totalSeconds.toFixed(totalSeconds >= 10 ? 1 : 2)
    return locale === 'zh-CN' ? `${renderedSeconds}秒` : `${renderedSeconds}s`
  }

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = Math.round(totalSeconds % 60)
  if (minutes < 60) {
    return locale === 'zh-CN' ? `${minutes}分 ${seconds}秒` : `${minutes}m ${seconds}s`
  }

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return locale === 'zh-CN' ? `${hours}小时 ${remainingMinutes}分` : `${hours}h ${remainingMinutes}m`
}
