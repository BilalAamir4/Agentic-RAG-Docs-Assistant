import { useEffect, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import examples from '@/data/examples.json'
import type { ExampleQuestion, PipelineInfo, PipelineName, PipelinesResponse } from '@/lib/api-types'
import {
  API_PIPELINES_PATH,
  DEFAULT_PIPELINE,
  EXAMPLE_PREVIEW_CHARS,
  MAX_QUESTION_CHARS,
  MIN_QUESTION_CHARS,
} from '@/lib/config'
import { truncate } from '@/lib/format'

/** Shown when GET /api/pipelines fails: the three names and labels, without descriptions. */
const FALLBACK_PIPELINES: PipelineInfo[] = [
  { name: 'baseline', label: 'Baseline RAG', description: '' },
  { name: 'corrective', label: 'Corrective RAG', description: '' },
  { name: 'self_rag', label: 'Self-RAG', description: '' },
]

type PipelineState =
  | { status: 'loading' }
  | { status: 'ready'; pipelines: PipelineInfo[] }
  | { status: 'failed'; pipelines: PipelineInfo[] }

/** Load the pipeline list from the API once. */
function usePipelines(): PipelineState {
  const [state, setState] = useState<PipelineState>({ status: 'loading' })
  useEffect(() => {
    let cancelled = false
    fetch(API_PIPELINES_PATH)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<PipelinesResponse>
      })
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', pipelines: data.pipelines })
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'failed', pipelines: FALLBACK_PIPELINES })
      })
    return () => {
      cancelled = true
    }
  }, [])
  return state
}

/** Radio group of pipelines, with Skeleton rows while loading and an Alert on failure. */
function PipelineChoice(props: {
  state: PipelineState
  value: PipelineName
  onChange: (name: PipelineName) => void
}) {
  const { state, value, onChange } = props
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-sm font-medium">Pipeline</legend>
      {state.status === 'failed' && (
        <Alert variant="destructive">
          <AlertTitle>Could not load the pipelines.</AlertTitle>
        </Alert>
      )}
      {state.status === 'loading' ? (
        <div className="flex flex-col gap-3" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (
        <RadioGroup
          value={value}
          onValueChange={(v) => onChange(v as PipelineName)}
          aria-label="Pipeline"
        >
          {state.pipelines.map((p) => (
            <div key={p.name} className="flex items-start gap-3">
              <RadioGroupItem
                value={p.name}
                id={`pipeline-${p.name}`}
                aria-describedby={p.description ? `pipeline-${p.name}-desc` : undefined}
                className="mt-0.5"
              />
              <div className="flex flex-col gap-0.5">
                <Label htmlFor={`pipeline-${p.name}`}>{p.label}</Label>
                {p.description && (
                  <p id={`pipeline-${p.name}-desc`} className="text-sm text-muted-foreground">
                    {p.description}
                  </p>
                )}
              </div>
            </div>
          ))}
        </RadioGroup>
      )}
    </fieldset>
  )
}

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

/**
 * The ask panel: question box, pipeline choice, examples and the Ask button.
 * Calls onAsk(question, pipeline) with the trimmed question; it does not submit itself.
 */
export function AskPanel(props: { onAsk: (question: string, pipeline: PipelineName) => void }) {
  const [question, setQuestion] = useState('')
  const [pipeline, setPipeline] = useState<PipelineName>(DEFAULT_PIPELINE)
  const pipelines = usePipelines()
  const canAsk = question.trim().length >= MIN_QUESTION_CHARS

  const submit = () => {
    if (canAsk) props.onAsk(question.trim(), pipeline)
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
            aria-describedby="question-count"
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            rows={3}
          />
          <p id="question-count" className="text-right text-xs text-muted-foreground">
            {question.length} / {MAX_QUESTION_CHARS}
          </p>
        </div>
        <PipelineChoice state={pipelines} value={pipeline} onChange={setPipeline} />
        <Examples onPick={setQuestion} />
        <div>
          <Button type="button" onClick={submit} disabled={!canAsk}>
            Ask
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
