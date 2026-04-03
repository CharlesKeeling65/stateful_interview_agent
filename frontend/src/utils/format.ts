const DISPLAY_TIME_ZONE = 'Asia/Shanghai'

export function parseApiDate(value: string) {
  const normalizedValue =
    /z|[+-]\d{2}:\d{2}$/i.test(value) ? value : `${value}Z`
  return new Date(normalizedValue)
}

export function parseApiDateMs(value: string) {
  return parseApiDate(value).getTime()
}

export function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: DISPLAY_TIME_ZONE,
    timeZoneName: 'short',
  }).format(parseApiDate(value))
}

export function formatDurationMs(value: number | null | undefined) {
  if (!value || value <= 0) {
    return '0s'
  }

  if (value < 1000) {
    return `${value}ms`
  }

  const totalSeconds = value / 1000
  if (totalSeconds < 60) {
    return `${totalSeconds.toFixed(totalSeconds >= 10 ? 1 : 2)}s`
  }

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = Math.round(totalSeconds % 60)
  if (minutes < 60) {
    return `${minutes}m ${seconds}s`
  }

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return `${hours}h ${remainingMinutes}m`
}
