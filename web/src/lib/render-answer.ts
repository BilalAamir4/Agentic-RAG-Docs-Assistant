/**
 * Splits answer text into blocks and inline parts. The result is plain data; it never contains
 * HTML, so the components render it as React elements and the text can never become markup.
 */

/** A piece of a paragraph. Text may contain \n, shown as a line break by CSS. */
export type InlinePart =
  | { kind: 'text'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'citation'; n: number; linked: boolean }

export type AnswerBlock =
  | { kind: 'paragraph'; parts: InlinePart[] }
  | { kind: 'code'; language: string; text: string }

/** Highest excerpt number treated as a citation marker. */
export const MAX_CITATION_NUMBER = 99

const FENCE_OPEN = /^\s*```([^\s`]*)\s*$/
const FENCE_CLOSE = /^\s*```\s*$/
// Leftmost match wins, so "[1]" inside a backtick span stays part of the code span.
const INLINE = /`([^`\n]+)`|\[([1-9]\d?)\]/g

/** Split one paragraph into text, inline code and citation parts. */
function tokenizeInline(text: string, sourceNumbers: Set<number>): InlinePart[] {
  const parts: InlinePart[] = []
  let last = 0
  for (const match of text.matchAll(INLINE)) {
    if (match.index > last) parts.push({ kind: 'text', text: text.slice(last, match.index) })
    if (match[1] !== undefined) {
      parts.push({ kind: 'code', text: match[1] })
    } else {
      const n = Number(match[2])
      if (n <= MAX_CITATION_NUMBER) {
        parts.push({ kind: 'citation', n, linked: sourceNumbers.has(n) })
      } else {
        parts.push({ kind: 'text', text: match[0] })
      }
    }
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push({ kind: 'text', text: text.slice(last) })
  return parts
}

/**
 * Tokenize answer text. Fenced code (``` with an optional language) becomes a verbatim code
 * block. Outside code, a blank line separates paragraphs and single newlines are kept.
 * [n] with n from 1 to 99 becomes a citation, linked when sourceNumbers has n.
 */
export function tokenizeAnswer(text: string, sourceNumbers: Set<number>): AnswerBlock[] {
  const blocks: AnswerBlock[] = []
  let paragraph: string[] = []
  let code: { language: string; lines: string[] } | null = null

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push({
        kind: 'paragraph',
        parts: tokenizeInline(paragraph.join('\n'), sourceNumbers),
      })
      paragraph = []
    }
  }

  for (const line of text.replace(/\r\n?/g, '\n').split('\n')) {
    if (code !== null) {
      if (FENCE_CLOSE.test(line)) {
        blocks.push({ kind: 'code', language: code.language, text: code.lines.join('\n') })
        code = null
      } else {
        code.lines.push(line)
      }
      continue
    }
    const open = FENCE_OPEN.exec(line)
    if (open) {
      flushParagraph()
      code = { language: open[1], lines: [] }
    } else if (line.trim() === '') {
      flushParagraph()
    } else {
      paragraph.push(line)
    }
  }
  if (code !== null) {
    blocks.push({ kind: 'code', language: code.language, text: code.lines.join('\n') })
  }
  flushParagraph()
  return blocks
}
