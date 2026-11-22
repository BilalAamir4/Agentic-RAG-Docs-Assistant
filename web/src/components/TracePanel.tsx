import { ChevronRightIcon } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { PipelineResult, TraceEvent } from '@/lib/api-types'
import { formatMs } from '@/lib/format'
import { outcomeStyle, TONE_CLASSES } from '@/lib/outcome'
import { chunkLabel, decisionReason, retrievalChunks } from '@/lib/trace'
import { cn } from '@/lib/utils'

/** Pixels from the bottom within which the list still counts as "scrolled to the bottom". */
const STICK_TOLERANCE_PX = 8

const ROW_BASE =
  'flex flex-col gap-1 py-1.5 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-300'

function TimeCell(props: { ms: number }) {
  return (
    <span className="w-14 shrink-0 text-xs tabular-nums text-muted-foreground">
      {formatMs(props.ms)}
    </span>
  )
}

/** A small, muted row for node_start and node_end. */
function NodeRow(props: { event: TraceEvent }) {
  const { event } = props
  return (
    <li className={cn(ROW_BASE, 'text-xs text-muted-foreground')} data-type={event.type}>
      <div className="flex gap-2">
        <TimeCell ms={event.t_ms} />
        <span className="font-mono">{event.node}</span>
        <span>{event.message}</span>
      </div>
    </li>
  )
}

/** A row with a plain time, node and message. Used for unknown types and retrieval without chunks. */
function PlainRow(props: { event: TraceEvent; children?: ReactNode }) {
  const { event } = props
  return (
    <li className={cn(ROW_BASE, 'text-sm')} data-type={event.type}>
      <div className="flex gap-2">
        <TimeCell ms={event.t_ms} />
        <span className="font-mono text-xs">{event.node}</span>
        <span className="min-w-0 break-words">{event.message}</span>
      </div>
      {props.children}
    </li>
  )
}

/** A retrieval row: the message, and a collapsible table of the chunks it returned. */
function RetrievalRow(props: { event: TraceEvent }) {
  const { event } = props
  const chunks = retrievalChunks(event.data)
  if (chunks.length === 0) return <PlainRow event={event} />
  return (
    <li className={cn(ROW_BASE, 'text-sm')} data-type="retrieval">
      <Collapsible>
        <div className="flex flex-wrap items-center gap-2">
          <TimeCell ms={event.t_ms} />
          <span className="font-mono text-xs">{event.node}</span>
          <CollapsibleTrigger className="group flex items-center gap-1 rounded-sm text-left outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <ChevronRightIcon
              className="size-4 transition-transform group-data-[state=open]:rotate-90 motion-reduce:transition-none"
              aria-hidden="true"
            />
            <span className="break-words">{event.message}</span>
            <span className="text-xs text-muted-foreground">show {chunks.length} chunks</span>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="mt-2 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">Rank</TableHead>
                <TableHead>Chunk</TableHead>
                <TableHead className="w-20 text-right">Score</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {chunks.map((c) => (
                <TableRow key={`${c.rank}-${c.chunk_id ?? c.url ?? c.title}`}>
                  <TableCell className="tabular-nums">{c.rank}</TableCell>
                  <TableCell className="whitespace-normal">{chunkLabel(c)}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.score.toFixed(3)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}

/** A prominent row for a decision: a 4 px left border and a badge, both from data.outcome. */
function DecisionRow(props: { event: TraceEvent }) {
  const { event } = props
  const outcome = event.data.outcome
  const style = outcomeStyle(outcome)
  const tone = TONE_CLASSES[style.tone]
  const reason = decisionReason(event.data)
  return (
    <li
      className={cn(ROW_BASE, 'rounded-r-md border-l-4 bg-muted/40 pl-3 text-sm', tone.border)}
      data-type="decision"
      data-node={event.node}
      data-outcome={typeof outcome === 'string' ? outcome : ''}
      data-tag={style.tag}
    >
      <div className="flex flex-wrap items-center gap-2">
        <TimeCell ms={event.t_ms} />
        <Badge variant="outline" className={tone.badge}>
          {style.tag}
        </Badge>
        <span className="font-mono text-xs">{event.node}</span>
        <span className="min-w-0 break-words font-medium">{event.message}</span>
      </div>
      {reason && <p className="pl-16 text-xs text-muted-foreground">{reason}</p>}
    </li>
  )
}

/** A red row for an error event. */
function ErrorRow(props: { event: TraceEvent }) {
  const { event } = props
  const tone = TONE_CLASSES.red
  return (
    <li
      className={cn(ROW_BASE, 'rounded-r-md border-l-4 pl-3 text-sm', tone.border)}
      data-type="error"
      data-node={event.node}
    >
      <div className="flex flex-wrap items-center gap-2">
        <TimeCell ms={event.t_ms} />
        <Badge variant="outline" className={tone.badge}>
          Error
        </Badge>
        <span className="font-mono text-xs">{event.node}</span>
        <span className="min-w-0 break-words">{event.message}</span>
      </div>
    </li>
  )
}

/** Choose the row for one event by its type. */
function EventRow(props: { event: TraceEvent }) {
  const { event } = props
  switch (event.type) {
    case 'node_start':
    case 'node_end':
      return <NodeRow event={event} />
    case 'retrieval':
      return <RetrievalRow event={event} />
    case 'decision':
      return <DecisionRow event={event} />
    case 'error':
      return <ErrorRow event={event} />
    default:
      return <PlainRow event={event} />
  }
}

/** Final row: total time, number of LLM calls and whether web search was used. */
function SummaryRow(props: { result: PipelineResult }) {
  const { result } = props
  return (
    <li
      className={cn(ROW_BASE, 'border-t pt-2 text-sm font-medium')}
      data-type="summary"
    >
      <span>
        Total {formatMs(result.latency_ms)} · {result.llm_calls} LLM calls ·{' '}
        {result.used_web ? 'web search used' : 'no web search'}
      </span>
    </li>
  )
}

/** Muted last row after the user pressed Stop. */
function StoppedRow() {
  return (
    <li className={cn(ROW_BASE, 'text-xs italic text-muted-foreground')} data-type="stopped">
      Stopped by you
    </li>
  )
}

/** Keep the list scrolled to the bottom while the user is already at the bottom. */
function useStickToBottom(count: number) {
  const ref = useRef<HTMLDivElement>(null)
  const stuck = useRef(true)
  useEffect(() => {
    if (count === 0) stuck.current = true
    const el = ref.current
    if (el && stuck.current) el.scrollTop = el.scrollHeight
  }, [count])
  const onScroll = () => {
    const el = ref.current
    if (el) stuck.current = el.scrollHeight - el.scrollTop - el.clientHeight <= STICK_TOLERANCE_PX
  }
  return { ref, onScroll }
}

/**
 * The trace timeline: one row per event in arrival order, then a summary row when the run
 * ends with an answer. From 900 px the list scrolls inside the card.
 */
export function TracePanel(props: {
  events: TraceEvent[]
  result: PipelineResult | null
  stopped: boolean
}) {
  const { events, result, stopped } = props
  const rowCount = events.length + (result ? 1 : 0) + (stopped ? 1 : 0)
  const { ref, onScroll } = useStickToBottom(rowCount)
  return (
    <Card className="min-[900px]:col-start-1 min-[900px]:row-start-2">
      <CardHeader>
        <CardTitle>
          <h2>Trace</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {rowCount === 0 && (
          <p className="text-sm text-muted-foreground">
            Ask a question to see each step the pipeline takes.
          </p>
        )}
        <div
          ref={ref}
          onScroll={onScroll}
          tabIndex={0}
          className={cn(
            'rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring',
            'min-[900px]:max-h-[70vh] min-[900px]:overflow-auto',
            rowCount === 0 && 'hidden',
          )}
        >
          <ol aria-label="Pipeline trace" className="flex flex-col divide-y divide-transparent">
            {events.map((event, i) => (
              <EventRow key={i} event={event} />
            ))}
            {result && <SummaryRow result={result} />}
            {stopped && <StoppedRow />}
          </ol>
        </div>
      </CardContent>
    </Card>
  )
}
