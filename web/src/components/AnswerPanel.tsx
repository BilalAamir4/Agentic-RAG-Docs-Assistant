import { InfoIcon } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { PipelineResult } from '@/lib/api-types'
import { MSG_STOPPED } from '@/lib/config'
import { tokenizeAnswer } from '@/lib/render-answer'
import type { AnswerBlock, InlinePart } from '@/lib/render-answer'
import type { RunState } from '@/lib/run-state'
import { buildSources } from '@/lib/sources'
import type { SourceEntry } from '@/lib/sources'

/** Separator between heading path parts. */
const HEADING_SEPARATOR = ' › '

/** One inline part as a React element. Text is a child, never markup. */
function Inline(props: { part: InlinePart }) {
  const { part } = props
  if (part.kind === 'code') {
    return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]">{part.text}</code>
  }
  if (part.kind === 'citation') {
    if (!part.linked) return <>[{part.n}]</>
    return (
      <sup>
        <a
          href={`#source-${part.n}`}
          aria-label={`Source ${part.n}`}
          className="text-primary underline-offset-2 hover:underline focus-visible:underline"
        >
          [{part.n}]
        </a>
      </sup>
    )
  }
  return <>{part.text}</>
}

/** The answer text as paragraphs and code blocks. */
function AnswerBody(props: { blocks: AnswerBlock[] }) {
  return (
    <div className="flex flex-col gap-3 text-sm">
      {props.blocks.map((block, i) =>
        block.kind === 'code' ? (
          <pre
            key={i}
            tabIndex={0}
            className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs"
          >
            <code>{block.text}</code>
          </pre>
        ) : (
          <p key={i} className="whitespace-pre-line break-words">
            {block.parts.map((part, j) => (
              <Inline key={j} part={part} />
            ))}
          </p>
        ),
      )}
    </div>
  )
}

function SourceItem(props: { source: SourceEntry }) {
  const { source } = props
  return (
    <li id={`source-${source.n}`} className="flex gap-2 text-sm">
      <span className="w-6 shrink-0 tabular-nums text-muted-foreground">{source.n}.</span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="flex flex-wrap items-center gap-2">
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="break-words font-medium text-primary underline-offset-2 hover:underline"
          >
            {source.title}
          </a>
          {source.isWeb && <Badge variant="outline">web</Badge>}
        </span>
        {source.headingPath.length > 0 && (
          <span className="break-words text-xs text-muted-foreground">
            {source.headingPath.join(HEADING_SEPARATOR)}
          </span>
        )}
      </div>
    </li>
  )
}

/** The Sources heading and numbered list. */
function Sources(props: { sources: SourceEntry[]; skipped: number; abstained: boolean }) {
  const { sources, skipped, abstained } = props
  if (sources.length === 0 && abstained) return null
  return (
    <section aria-labelledby="sources-heading" className="flex flex-col gap-2">
      <h3 id="sources-heading" className="text-sm font-semibold">
        Sources
      </h3>
      {sources.length === 0 ? (
        <p className="text-sm text-muted-foreground">No sources were cited.</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {sources.map((s) => (
            <SourceItem key={s.chunkId} source={s} />
          ))}
        </ol>
      )}
      {skipped > 0 && (
        <p className="text-xs text-muted-foreground">
          {skipped} cited source{skipped === 1 ? '' : 's'} could not be matched to a retrieved chunk.
        </p>
      )}
    </section>
  )
}

/** A finished answer: the text (or abstention notice) and the Sources. */
function FinishedAnswer(props: { result: PipelineResult }) {
  const { answer } = props.result
  const { sources, skipped } = buildSources(props.result)
  const blocks = tokenizeAnswer(answer.text, new Set(sources.map((s) => s.n)))
  return (
    <div className="flex flex-col gap-4">
      {answer.abstained ? (
        <Alert>
          <InfoIcon aria-hidden="true" />
          <AlertTitle>The docs do not answer this question.</AlertTitle>
          <AlertDescription>
            <AnswerBody blocks={blocks} />
          </AlertDescription>
        </Alert>
      ) : (
        <AnswerBody blocks={blocks} />
      )}
      <Sources sources={sources} skipped={skipped} abstained={answer.abstained} />
    </div>
  )
}

/** Errors shown here; "input" and "rate" belong to the ask panel. */
function showsHere(state: RunState): boolean {
  return state.error !== null && state.error.kind !== 'input' && state.error.kind !== 'rate'
}

/**
 * The answer card: Skeleton lines while running, the answer with Sources when done, and a
 * destructive Alert for server, network and stream errors. A polite live region.
 */
export function AnswerPanel(props: { state: RunState }) {
  const { state } = props
  const running = state.status === 'running'
  return (
    <Card className="min-[900px]:col-start-2 min-[900px]:row-start-2">
      <CardHeader>
        <CardTitle>
          <h2>Answer</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div role="region" aria-label="Answer" aria-live="polite" aria-busy={running}>
          {state.result && <FinishedAnswer result={state.result} />}
          {running && !state.result && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          )}
          {showsHere(state) && state.error && (
            <Alert variant="destructive">
              <AlertTitle>{state.error.message}</AlertTitle>
            </Alert>
          )}
          {state.status === 'stopped' && !state.result && (
            <Alert>
              <InfoIcon aria-hidden="true" />
              <AlertTitle>{MSG_STOPPED}</AlertTitle>
            </Alert>
          )}
          {state.status === 'idle' && (
            <p className="text-sm text-muted-foreground">The answer and its sources appear here.</p>
          )}
          {state.status === 'failed' && !showsHere(state) && (
            <p className="text-sm text-muted-foreground">No answer was produced.</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
