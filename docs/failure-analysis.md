# Failure analysis

Sources: `results/failure_labels.csv` (final_label column), `results/failure_review.md`, `results/summary.md`, `results/analysis_notes.md`, and the runs `results/runs/baseline-20261116-1050`, `results/runs/corrective-20261120-1852`, `results/runs/self_rag-20261121-0744`. A failed item is an answerable question whose judge correctness is below 2 (an abstention counts as 0), or an unanswerable question that was answered. The benchmark has 50 questions: 42 answerable, 8 unanswerable. All 8 unanswerable questions were declined by all three pipelines, so every failed item below is an answerable question.

Labels were assigned by the automatic rules in `src/ragdocs/eval/failure_review.py`, except two items that the rules left open (corrective q034 and self_rag q033). Those two were decided by hand: corrective q034 `unfaithful_generation`, self_rag q033 `judge_disagreement`.

## Label counts per pipeline

| final_label | baseline | corrective | self_rag | total |
|---|---|---|---|---|
| retrieval_miss | 3 | 3 | 3 | 9 |
| false_abstention | 1 | 1 | 1 | 3 |
| router_out_of_scope | 0 | 0 | 1 | 1 |
| unfaithful_generation | 0 | 1 | 0 | 1 |
| judge_disagreement | 0 | 0 | 1 | 1 |
| failed items (of 42 answerable) | 4 | 5 | 6 | 15 |

Labels that were allowed but did not occur: structured_output_failure, grading_drop, hallucinated_unanswerable, web_used_failure, rewrite_drift, stale_web_content, incomplete_answer, verifier_false_alarm.

The three pipelines fail on the same questions for the most part: q008, q024, q025 and q029 fail in all three. The differences are q034 (corrective only), q028 (self_rag only) and q033 (self_rag only).

LangSmith links: the committed files hold the LangSmith run id of each item (`langsmith_run_id` in `per_question.jsonl`), not a trace URL, so run ids are given instead of links.

## retrieval_miss (baseline 3, corrective 3, self_rag 3)

What it is: no gold evidence section in the first retrieval's top 5 chunks. Matching is strict at the section anchor (`doc_path#anchor`).

Items: q008, q024 and q025 in every pipeline.

- q008 (all three pipelines, correctness 0). Gold anchor `checkpointers.mdx#get-state-history` is not in the first top 5. self_rag trace: `grade_documents: 2 of 5 chunks relevant`, `generate: Generating from 2 graded excerpts and 0 web results`, `verify_answer: verification skipped: abstained`. The answer was "I couldn't find this in the LangGraph documentation." LangSmith run ids: baseline `01a1e3fe-2855-7953-9722-5e0a0faef354`.
- q025 (all three, correctness 0). Gold anchor `errors/INVALID_GRAPH_NODE_RETURN_VALUE.mdx#` is not in the first top 5. corrective trace: `grade_documents: 0 of 5 chunks relevant`, `Route to rewrite_query`, `query rewritten`, `grade_documents: 0 of 5 chunks relevant`, `Route to web_search: too few relevant chunks after 1 rewrite(s)`, `generate: Generating from 0 graded excerpts and 3 web results`. Both agentic pipelines went to web search and still did not answer. LangSmith run id: self_rag q025 `01a20285-2cfa-7e71-8edc-5db80617673b`.
- q024 (baseline 1, corrective 0, self_rag 1). Gold anchor `errors/INVALID_CONCURRENT_GRAPH_UPDATE.mdx#` is not in the first top 5. The retrieved page `use-graph-api#run-graph-nodes-in-parallel` covers parallel branches. The baseline judge says the answer "misses mentioning reducers"; the corrective judge says it attributes the failure to ordering and misses reducers. corrective trace: `grade_documents: 1 of 5 chunks relevant`, `generate: Generating from 1 graded excerpts and 0 web results`. self_rag passed 2 chunks and verify accepted the answer first time. LangSmith run ids: corrective `01a1fa7d-037e-7071-a305-e7c49daddb43`, self_rag `01a20284-3119-7630-98c0-2a90de720479`.

Likely fix (untested): index the error pages with their error names in the chunk text, or let the evidence match accept a parent or child section of the gold anchor. The second would change how the benchmark scores and is not a retrieval improvement.

## false_abstention (baseline 1, corrective 1, self_rag 1)

What it is: an answerable question where the pipeline answered "I couldn't find this in the LangGraph documentation."

Item: q029 in every pipeline ("How do I set up a graph with SQLite persistence and resume an interrupted thread?", a multi-hop question).

- corrective trace: `grade_documents: 5 of 5 chunks relevant`, `Route to generate: 5 relevant chunk(s) >= 1`, `generate: Generating from 5 graded excerpts and 0 web results`. self_rag has the same path plus `verify_answer: verification skipped: abstained`. The grader accepted all 5 chunks and the generator still abstained, so the abstention did not come from retrieval or grading. The files do not show why the generator abstained. LangSmith run ids: corrective `01a1fa80-f0a7-7610-a3c0-5383071439fc`.

Likely fix (untested): a generator prompt that prefers a partial answer from the excerpts over a full abstention. The answer prompt is shared by all three pipelines, so a change needs a new entry in `docs/DECISIONS.md` and a new run of all three.

## router_out_of_scope (self_rag 1)

What it is: the self-RAG router (`decide_retrieval`) sent an answerable question to `out_of_scope`.

Item: q028 ("In Pregel, which channel is used by default, and what happens to earlier values?"). Trace: `decide_retrieval: no retrieval needed: Question about Pregel, not LangGraph.`, `out_of_scope: out of scope; answered without retrieval`. Correctness 2 in baseline and corrective, 0 in self_rag. There is no retrieval event, so it also counts as a first-retrieval hit@5 miss: this accounts for the whole 1-question gap in first-retrieval hit@5 between self_rag (33/42) and corrective (34/42). LangSmith run id: `01a20288-31e6-75b3-8410-73963e17b608`.

This was pre-registered before the run (results/analysis_notes.md, section 2, item 5). The router prompt was not tuned on the eval set.

Likely fix (untested): list Pregel and other LangGraph internals as in scope in the router prompt. Not done, because tuning on this question would use the eval set as a training signal.

## unfaithful_generation (corrective 1)

What it is: the answer states something that its excerpts do not support.

Item: corrective q034 ("How do I read the saved state of a thread and then edit it?"), correctness 1. The answer says to edit state with a node "decorated with `@update_state`"; the reference uses `graph.update_state(config, values)`. Judge: "invents an incorrect API for updating state by suggesting an '@update_state' decorator". RAGAS faithfulness 0.727. Trace: `grade_documents: 4 of 5 chunks relevant`, `generate: Generating from 4 graded excerpts and 0 web results`, and no verification step. self_rag took the same first path, its `verify_answer` flagged the unsupported claim `or graph.update_state(...)`, `regenerate` ran once, and the second verification passed; self_rag q034 has correctness 2. LangSmith run ids: corrective `01a1fa84-e169-7950-9891-e330f50c132e`, self_rag `01a2028d-3b91-7351-a67f-dde88b42908e`.

Likely fix (untested): a verification step after generation, which is what self_rag has. This one item is the only evidence for it in these runs.

## judge_disagreement (self_rag 1)

What it is: the judge's verdict looks wrong against the reference answer.

Item: self_rag q033 ("... print the parent agent's own tokens and also follow each sub-agent's messages from a single streaming run?"), judge correctness 1, citation_support 0. The judge wrote that the answer "invents a stream.subgraphs property on stream_events output". The reference answer itself iterates `stream.subgraphs` after `graph.stream_events(input, version="v3")`. RAGAS faithfulness is 1.000. Trace: `grade_documents: 3 of 5 chunks relevant`, `generate: Generating from 3 graded excerpts and 0 web results`, `verify_answer: answer verified`. No score was changed, because there is no rescoring: the committed score for q033 stays at correctness 1 and counts against self_rag in every table. LangSmith run id: `01a2028c-3903-7693-aaeb-134af396fc7f`.

The full stored answer (`per_question.jsonl`, q033) contains two snippets. The first uses `graph.stream(..., subgraphs=True)`. The second is `graph.stream_events(input, version="v3")` followed by `for subgraph in stream.subgraphs:` reading `subgraph.graph_name`, `subgraph.path` and `subgraph.messages`, which is the method of the reference answer. The 600-character excerpt in `failure_review.md` cuts the answer before that snippet. The judge's stated reason therefore contradicts the reference and the answer, and the label records that.

Likely fix (untested): a second judge pass or a larger hand audit. The hand audit covered 11 items (judge agreement 10/11 on correctness, 11/11 on citation support, run baseline-20261116-1050), but that audit covered only the baseline run, so no self_rag item was audited.

## What each technique actually fixed

Counts of questions whose judge correctness changed (0 to 2 scale; abstained counts as 0). Source: the changed-questions lists in `results/summary.md` and section 1 and 4 of `results/analysis_notes.md`. Noise rule (D19): a difference under 3 questions is no measurable difference.

Ceiling: the baseline answered 38 of 42 answerable questions correctly (correctness 2). At most 4 questions (q008, q024, q025, q029) were left for any technique to fix.

### Baseline to corrective RAG

- Fixed: none. None of the 4 questions the baseline failed reached correctness 2.
- Broken: q034 (2 to 1, `unfaithful_generation`) and q024 (1 to 0, the single retrieved chunk the grader kept did not mention reducers).
- Net: 0 better, 2 worse on paired correctness. Correct answers 38 to 37 of 42 (-1). Verdict: no measurable difference.
- What it did do: it ran web search on 8 of 50 questions (baseline 0 of 50), a measurable difference of +8. Web results did not turn any of the failed items into a correct one: q025, the only failed answerable item that went to web search, stayed an abstention.

### Corrective RAG to self-RAG

- Fixed: q034 (1 to 2; verify flagged an unsupported claim, one regeneration, second verify passed) and q024 (0 to 1; the grader kept 2 chunks instead of 1, and no regeneration ran, so this is not a verify effect).
- Broken: q028 (2 to 0, `router_out_of_scope`) and q033 (2 to 1, `judge_disagreement`).
- Net: 2 better, 2 worse. Correct answers 37 to 36 of 42 (-1). Verdict: no measurable difference.
- Regeneration ran on 4 of 50 items (q006, q017, q032, q034); of these only q034 changed its outcome.

### Baseline to self-RAG

- Fixed: none. Broken: q028 (2 to 0) and q033 (2 to 1).
- Net: 0 better, 2 worse. Correct answers 38 to 36 of 42 (-2). Verdict: no measurable difference.

### Reading

Neither technique fixed any of the 4 questions that the baseline failed to answer correctly. The differences in correct-answer counts (-1, -1, -2) are all under the 3-question threshold. RAGAS faithfulness, response relevancy, context precision and context recall have no measurable difference for any pair either (wins minus losses at most 2 in absolute value, against a threshold of 3; see the README results block). The one measurable difference in the count metrics is the number of questions that used web search (+8 and +7 questions against the baseline). Cost per question is also higher: mean tokens 2,334 (baseline), 4,577 (corrective) and 6,847 (self_rag), p95 latency 3.7 s, 8.0 s and 9.2 s. Cost rows are measured values and carry no noise verdict.

Note: `results/failure_review.md` is the generated file from before the labels were decided; it still shows self_rag q033 as `unfaithful_generation (proposed)`. The final labels are in `results/failure_labels.csv`, and this document follows the CSV.
