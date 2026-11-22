import { AnswerPanel } from '@/components/AnswerPanel'
import { AskPanel } from '@/components/AskPanel'
import { Header } from '@/components/Header'
import { ResultsTable } from '@/components/ResultsTable'
import { TracePanel } from '@/components/TracePanel'
import { useAskRun } from '@/hooks/use-ask-run'

/**
 * Page layout. Below 900 px: header, ask, answer, trace, results.
 * From 900 px: a full-width ask panel, then trace (left) and answer (right), then results.
 * Owns the run state (idle, running, done, failed) through useAskRun.
 */
export default function App() {
  const { state, start, stop } = useAskRun()
  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 pb-12">
      <Header />
      <main className="flex flex-col gap-6">
        <div className="grid gap-4 min-[900px]:grid-cols-2">
          <AskPanel
            onAsk={start}
            onStop={stop}
            running={state.status === 'running'}
            stopped={state.status === 'stopped'}
            error={state.error}
            retryLeft={state.retryLeft}
          />
          <AnswerPanel state={state} />
          <TracePanel
            events={state.events}
            result={state.result}
            stopped={state.status === 'stopped'}
          />
        </div>
        <ResultsTable />
      </main>
    </div>
  )
}
