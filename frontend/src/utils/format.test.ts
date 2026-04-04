import { describe, expect, it } from 'vitest'

import { formatDurationMs, formatTimestamp } from './format'

describe('format helpers', () => {
  it('formats durations concisely for short and long spans', () => {
    expect(formatDurationMs(850, 'en')).toBe('850ms')
    expect(formatDurationMs(12_300, 'en')).toBe('12.3s')
    expect(formatDurationMs(121_000, 'zh-CN')).toBe('2分 1秒')
  })

  it('formats timestamps in the selected locale and Shanghai timezone', () => {
    const value = '2026-04-04T08:30:00'

    expect(formatTimestamp(value, 'en')).toContain('Apr')
    expect(formatTimestamp(value, 'zh-CN')).toContain('4月')
  })
})
