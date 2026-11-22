import { Alert, AlertTitle } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Skeleton } from '@/components/ui/skeleton'
import type { PipelineState } from '@/hooks/use-pipelines'
import type { PipelineName } from '@/lib/api-types'

/** Radio group of pipelines, with Skeleton rows while loading and an Alert on failure. */
export function PipelineChoice(props: {
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
