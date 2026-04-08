const MARKDOWN_EMPHASIS_PATTERN = /(\*\*|__)/g

function normalizeLineEndings(value: string) {
  return value.replace(/\r\n/g, '\n')
}

function stripDuplicatedQuestionPrefix(value: string) {
  const matches = [...value.matchAll(/Q(\d+)\s*:/gi)]
  if (matches.length < 2) {
    return value
  }

  const [first, second] = matches
  if (
    first.index !== undefined &&
    second.index !== undefined &&
    first.index < 4 &&
    second.index < 20 &&
    first[1] === second[1]
  ) {
    return value.slice(second.index)
  }

  return value
}

function cleanupQuestionPrefix(value: string) {
  return value
    .replace(/^\s*\*\*\s*(Q\d+\s*:)\s*\*\*\s*/i, '$1 ')
    .replace(/^\s*(Q\d+\s*:)\s*(Q\d+\s*:)\s*/i, (_full, first: string, second: string) =>
      first.toLowerCase() === second.toLowerCase() ? `${first} ` : `${first}${second} `,
    )
}

function stripMarkdownArtifacts(value: string) {
  return value.replace(MARKDOWN_EMPHASIS_PATTERN, '')
}

function trimParagraphSpacing(value: string) {
  return value
    .split('\n')
    .map((line) => line.trimEnd())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function normalizeQuestionText(value: string) {
  const normalized = trimParagraphSpacing(
    stripMarkdownArtifacts(
      cleanupQuestionPrefix(stripDuplicatedQuestionPrefix(normalizeLineEndings(value))),
    ),
  )

  return normalized.replace(/^\s*(Q\d+\s*:)\s*/i, '$1 ')
}

export function normalizeAnswerText(value: string | null | undefined) {
  if (!value) {
    return ''
  }

  return trimParagraphSpacing(
    stripMarkdownArtifacts(normalizeLineEndings(value)),
  ).replace(/^\s*(?:Q|Question)\s*\d+\s*[:：]\s*/i, '')
}

export function buildQuestionVersionDiff(previousText: string, nextText: string) {
  const previous = normalizeQuestionText(previousText)
  const next = normalizeQuestionText(nextText)
  const previousTokens = previous.split(/(\s+)/)
  const nextTokens = next.split(/(\s+)/)

  let prefixLength = 0
  while (
    prefixLength < previousTokens.length &&
    prefixLength < nextTokens.length &&
    previousTokens[prefixLength] === nextTokens[prefixLength]
  ) {
    prefixLength += 1
  }

  let previousSuffixIndex = previousTokens.length - 1
  let nextSuffixIndex = nextTokens.length - 1
  while (
    previousSuffixIndex >= prefixLength &&
    nextSuffixIndex >= prefixLength &&
    previousTokens[previousSuffixIndex] === nextTokens[nextSuffixIndex]
  ) {
    previousSuffixIndex -= 1
    nextSuffixIndex -= 1
  }

  const sharedPrefix = previousTokens.slice(0, prefixLength).join('')
  const sharedSuffix =
    previousSuffixIndex + 1 < previousTokens.length ? previousTokens.slice(previousSuffixIndex + 1).join('') : ''
  const before = previousTokens.slice(prefixLength, previousSuffixIndex + 1).join('')
  const after = nextTokens.slice(prefixLength, nextSuffixIndex + 1).join('')

  return {
    shared: `${sharedPrefix}${sharedSuffix}`,
    sharedPrefix,
    sharedSuffix,
    before,
    after,
    hasChanges: before !== after,
  }
}
