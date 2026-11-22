import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

/** Answer card. Session 1 shows the empty state only; session 2 renders the answer and sources. */
export function AnswerPanel() {
  return (
    <Card className="min-[900px]:col-start-2 min-[900px]:row-start-2">
      <CardHeader>
        <CardTitle>
          <h2>Answer</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">The answer and its sources appear here.</p>
      </CardContent>
    </Card>
  )
}
