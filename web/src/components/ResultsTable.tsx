import { useEffect, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { ResultsFile } from '@/lib/api-types'
import { RESULTS_PATH, SUMMARY_URL } from '@/lib/config'
import { formatMetric } from '@/lib/format'

const NOTE =
  '50 questions over a pinned snapshot of the LangGraph docs; correctness judged by an LLM audited by hand on 10 items; RAGAS metrics scored by Gemini; differences under the noise margin are not meaningful.'

/** Fetch results.json once. Returns the file, an error flag and a loading flag. */
function useResults(): { results: ResultsFile | null; failed: boolean } {
  const [results, setResults] = useState<ResultsFile | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let cancelled = false
    fetch(RESULTS_PATH)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<ResultsFile>
      })
      .then((data) => {
        if (!cancelled) setResults(data)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [])
  return { results, failed }
}

/** The "How the pipelines compare" section: one row per metric, one column per pipeline. */
export function ResultsTable() {
  const { results, failed } = useResults()
  const first = results?.pipelines[0]
  return (
    <section aria-labelledby="results-heading" className="flex flex-col gap-3">
      <h2 id="results-heading" className="text-xl font-semibold">
        How the pipelines compare
      </h2>
      {failed && (
        <Alert variant="destructive">
          <AlertTitle>Could not load the results.</AlertTitle>
          <AlertDescription>Reload the page to try again.</AlertDescription>
        </Alert>
      )}
      {!failed && !results && <Skeleton className="h-64 w-full" />}
      {results && first && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Metric</TableHead>
              {results.pipelines.map((p) => (
                <TableHead scope="col" key={p.name}>
                  {p.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(first.metrics).map(([key, metric]) => (
              <TableRow key={key}>
                <TableHead scope="row" className="whitespace-normal font-normal">
                  {metric.label}
                </TableHead>
                {results.pipelines.map((p) => (
                  <TableCell key={p.name}>{formatMetric(p.metrics[key])}</TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <p className="text-sm text-muted-foreground">{NOTE}</p>
      <p className="text-sm">
        <a
          className="underline underline-offset-4 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 outline-none rounded-sm"
          href={SUMMARY_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          Full comparison
        </a>
      </p>
    </section>
  )
}
