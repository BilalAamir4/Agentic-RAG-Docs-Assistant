import { AnswerPanel } from '@/components/AnswerPanel'
import { AskPanel } from '@/components/AskPanel'
import { Header } from '@/components/Header'
import { ResultsTable } from '@/components/ResultsTable'
import { TracePanel } from '@/components/TracePanel'
import type { PipelineName } from '@/lib/api-types'

/** Session 1 placeholder; session 2 replaces it with the streaming call. */
function handleAsk(question: string, pipeline: PipelineName): void {
  // TODO(S2): POST /api/ask and render the trace and answer.
  void question
  void pipeline
}

/**
 * Page layout. Below 900 px: header, ask, answer, trace, results.
 * From 900 px: a full-width ask panel, then trace (left) and answer (right), then results.
 */
export default function App() {
  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 pb-12">
      <Header />
      <main className="flex flex-col gap-6">
        <div className="grid gap-4 min-[900px]:grid-cols-2">
          <AskPanel onAsk={handleAsk} />
          <AnswerPanel />
          <TracePanel />
        </div>
        <ResultsTable />
      </main>
    </div>
  )
}
