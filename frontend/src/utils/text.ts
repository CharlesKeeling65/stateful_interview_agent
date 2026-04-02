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

  return trimParagraphSpacing(stripMarkdownArtifacts(normalizeLineEndings(value)))
}
