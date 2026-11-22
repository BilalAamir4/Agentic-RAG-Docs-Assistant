import { Loader2Icon } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { PipelineChoice } from '@/components/PipelineChoice'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import examples from '@/data/examples.json'
import { usePipelines } from '@/hooks/use-pipelines'
import type { ExampleQuestion, PipelineName } from '@/lib/api-types'
import {
  DEFAULT_PIPELINE,
  EXAMPLE_PREVIEW_CHARS,
  MAX_QUESTION_CHARS,
} from '@/lib/config'
import type { AskError } from '@/lib/ask'
import { truncate } from '@/lib/format'
import { canSubmit } from '@/lib/run-state'

/** Four example questions; clicking one fills the textarea and does not submit. */
function Examples(props: { onPick: (question: string) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium">Examples</p>
      <div className="grid gap-2 min-[600px]:grid-cols-2">
        {(examples as ExampleQuestion[]).map((e) => (
          <Button
            key={e.id}
            type="button"
            variant="secondary"
            className="h-auto justify-start gap-2 py-2 text-left whitespace-normal"
            onClick={() => props.onPick(e.question)}
          >
            <Badge variant="outline">{e.label}</Badge>
            <span>{truncate(e.question, EXAMPLE_PREVIEW_CHARS)}</span>
          </Button>
        ))}
      </div>
    </div>
  )
}

/** id of the Ask button; focus moves to it after the user presses Stop. */
const ASK_BUTTON_ID = 'ask-button'

/** What the ask panel needs to know about the current run. */
export interface AskPanelProps {
  onAsk: (question: string, pipeline: PipelineName) => void
  /** Abort the current run (the Stop button, shown only while running). */
  onStop: () => void
  /** True after the user stopped a run; focus then moves to Ask. */
  stopped: boolean
  /** True while a stream is open; Ask is disabled and shows "Running…". */
  running: boolean
  /** The last run's error. Only kinds "input" and "rate" are shown here. */
  error: AskError | null
  /** Seconds until Ask is allowed again after a 429. */
  retryLeft: number
}

/** The Ask button: a spinner and "Running…" while a run is open. */
function AskButton(props: { running: boolean; disabled: boolean; onClick: () => void }) {
  return (
    // aria-disabled, not the disabled attribute: a button that becomes disabled while it has
    // focus loses it, and focus must stay where it was when a run starts. submit() ignores
    // clicks and Enter while the button is unavailable.
    <Button
      id={ASK_BUTTON_ID}
      type="button"
      onClick={props.onClick}
      aria-disabled={props.disabled}
      aria-busy={props.running}
      className="aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
    >
      {props.running ? (
        <>
          <Loader2Icon className="motion-safe:animate-spin" aria-hidden="true" />
          Running…
        </>
      ) : (
        'Ask'
      )}
    </Button>
  )
}

/** The 429 message with a once-per-second "Try again in N s". */
function RateAlert(props: { message: string; retryLeft: number }) {
  return (
    <Alert>
      <AlertTitle>{props.message}</AlertTitle>
      <AlertDescription>Try again in {props.retryLeft} s</AlertDescription>
    </Alert>
  )
}

/**
 * The ask panel: question box, pipeline choice, examples and the Ask button.
 * Calls onAsk(question, pipeline) with the trimmed question. Ask is disabled while running,
 * during a rate-limit countdown, and while the trimmed question is under 3 characters.
 */
export function AskPanel(props: AskPanelProps) {
  const { onAsk, onStop, running, stopped, error, retryLeft } = props
  const [question, setQuestion] = useState('')
  const [pipeline, setPipeline] = useState<PipelineName>(DEFAULT_PIPELINE)
  const pipelines = usePipelines()
  const rateLimited = error?.kind === 'rate' && retryLeft > 0
  const inputError = error?.kind === 'input' ? error.message : null
  const canAsk = canSubmit(question, running, rateLimited)

  useEffect(() => {
    if (stopped) document.getElementById(ASK_BUTTON_ID)?.focus()
  }, [stopped])

  const submit = () => {
    if (canAsk) onAsk(question.trim(), pipeline)
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <Card className="min-[900px]:col-span-2">
      <CardHeader>
        <CardTitle>
          <h2>Ask a question</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <Label htmlFor="question">Your question</Label>
          <Textarea
            id="question"
            value={question}
            maxLength={MAX_QUESTION_CHARS}
            aria-describedby={inputError ? 'question-error question-count' : 'question-count'}
            aria-invalid={inputError ? true : undefined}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            rows={3}
          />
          {inputError && (
            <p id="question-error" className="text-sm text-destructive">
              {inputError}
            </p>
          )}
          <p id="question-count" className="text-right text-xs text-muted-foreground">
            {question.length} / {MAX_QUESTION_CHARS}
          </p>
        </div>
        <PipelineChoice state={pipelines} value={pipeline} onChange={setPipeline} />
        <Examples onPick={setQuestion} />
        {rateLimited && error && <RateAlert message={error.message} retryLeft={retryLeft} />}
        <div>
          <div className="flex gap-2">
            <AskButton running={running} disabled={!canAsk} onClick={submit} />
            {running && (
              <Button type="button" variant="outline" onClick={onStop}>
                Stop
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
