import { describe, expect, it } from 'vitest'

import {
  type Locale,
  createTranslator,
  getDisplayStageLabel,
  getReviewVerdictLabel,
} from './i18n'

describe('i18n display helpers', () => {
  it('translates common interface copy to Chinese', () => {
    const t = createTranslator('zh-CN')

    expect(t('app.title')).toBe('Stateful Interview Agent')
    expect(t('status.start')).toBe('开始访谈')
    expect(t('composer.submit')).toBe('提交回答并生成下一问')
  })

  it('keeps English copy available', () => {
    const t = createTranslator('en')

    expect(t('status.start')).toBe('Start interview')
    expect(t('sidebar.recentSessions')).toBe('Recent sessions')
  })

  it.each([
    ['en', 'architecture_understanding', 'Architecture Understanding'],
    ['zh-CN', 'architecture_understanding', '架构理解'],
    ['zh-CN', 'code_detail_completion', '代码细节补全'],
  ] as const)('formats stage labels for %s', (locale, rawStage, expected) => {
    expect(getDisplayStageLabel(rawStage, locale)).toBe(expected)
  })

  it.each([
    ['en', 'drifted', 'Drifted'],
    ['zh-CN', 'drifted', '已跑偏'],
    ['zh-CN', 'insufficient', '信息不足'],
  ] as const)('formats human review verdicts for %s', (locale, verdict, expected) => {
    expect(getReviewVerdictLabel(verdict, locale as Locale)).toBe(expected)
  })
})

