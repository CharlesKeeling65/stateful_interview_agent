import { useEffect, useMemo, useState } from 'react'

import type { Locale } from '../../i18n'
import { formatDurationMs, parseApiDateMs } from '../../utils/format'
import { PretextLiveText } from './PretextLiveText'

type PretextElapsedTimeProps = {
  className?: string
  endedAt?: string | null
  locale?: Locale
  startedAt: string
}

export function PretextElapsedTime({
  className,
  endedAt,
  locale = 'en',
  startedAt,
}: PretextElapsedTimeProps) {
  const startedAtMs = useMemo(() => parseApiDateMs(startedAt), [startedAt])
  const endedAtMs = useMemo(
    () => (endedAt ? parseApiDateMs(endedAt) : null),
    [endedAt],
  )
  const [now, setNow] = useState(() => endedAtMs ?? Date.now())

  useEffect(() => {
    if (endedAtMs) {
      return
    }

    const timer = window.setInterval(() => {
      setNow(Date.now())
    }, 500)

    return () => window.clearInterval(timer)
  }, [endedAtMs])

  return (
    <PretextLiveText
      className={className}
      text={formatDurationMs(Math.max(0, (endedAtMs ?? now) - startedAtMs), locale)}
    />
  )
}
