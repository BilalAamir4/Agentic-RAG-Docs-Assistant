import { CodeXmlIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { REPO_URL } from '@/lib/config'

/** Page header: the h1, the subtitle and the link to the source repository. */
export function Header() {
  return (
    <header className="flex flex-col gap-3 py-6 min-[600px]:flex-row min-[600px]:items-start min-[600px]:justify-between">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">LangGraph Docs Assistant</h1>
        <p className="max-w-2xl text-muted-foreground">
          Ask a question about the LangGraph Python docs and watch how baseline, corrective and
          self-RAG pipelines handle it.
        </p>
      </div>
      <Button asChild variant="outline">
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
          <CodeXmlIcon aria-hidden="true" />
          Source on GitHub
        </a>
      </Button>
    </header>
  )
}
