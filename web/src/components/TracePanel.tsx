import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

/** Trace card. Session 1 shows the empty state only; session 2 renders the streamed events. */
export function TracePanel() {
  return (
    <Card className="min-[900px]:col-start-1 min-[900px]:row-start-2">
      <CardHeader>
        <CardTitle>
          <h2>Trace</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Ask a question to see each step the pipeline takes.
        </p>
      </CardContent>
    </Card>
  )
}
