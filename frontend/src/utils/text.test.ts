import { describe, expect, it } from 'vitest'

import { buildQuestionVersionDiff, normalizeAnswerText } from './text'

describe('buildQuestionVersionDiff', () => {
  it('detects unchanged text', () => {
    const diff = buildQuestionVersionDiff(
      'Q2: Which modules coordinate the core workflow end to end?',
      'Q2: Which modules coordinate the core workflow end to end?',
    )

    expect(diff.hasChanges).toBe(false)
    expect(diff.before).toBe('')
    expect(diff.after).toBe('')
    expect(diff.shared).toContain('core workflow')
  })

  it('extracts shared prefix/suffix and changed middle', () => {
    const diff = buildQuestionVersionDiff(
      'Q2: Which modules coordinate the core workflow end to end?',
      'Q2: Which modules coordinate the user-facing workflow across services end to end?',
    )

    expect(diff.hasChanges).toBe(true)
    expect(diff.sharedPrefix).toBe('Q2: Which modules coordinate the ')
    expect(diff.before).toContain('core')
    expect(diff.after).toContain('user-facing')
    expect(diff.sharedSuffix).toContain(' end to end?')
  })
})

describe('normalizeAnswerText', () => {
  it('strips question-number prefixes from answers', () => {
    expect(normalizeAnswerText('Q1: The app starts in app/main.py')).toBe(
      'The app starts in app/main.py',
    )
    expect(normalizeAnswerText('Question 12: It loads config first.')).toBe(
      'It loads config first.',
    )
    expect(normalizeAnswerText('**Q1:** The app starts in app/main.py')).toBe(
      'The app starts in app/main.py',
    )
    expect(normalizeAnswerText('Q1：The app starts in app/main.py')).toBe(
      'The app starts in app/main.py',
    )
    expect(normalizeAnswerText('Q 2: The app starts in app/main.py')).toBe(
      'The app starts in app/main.py',
    )
    expect(normalizeAnswerText('**Question 2：** The app starts in app/main.py')).toBe(
      'The app starts in app/main.py',
    )
  })
})
