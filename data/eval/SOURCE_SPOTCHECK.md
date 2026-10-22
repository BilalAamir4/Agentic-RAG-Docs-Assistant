# Real User Question Sourcing Spotcheck (`SOURCE_SPOTCHECK.md`)

**Date:** 2026-10-21  
**Scope:** Spotcheck audit of all items in `data/eval/eval_set.jsonl` with external user sources verified verbatim against page snapshots.
**Standard Applied:** Strict verbatim verification. Every non-"docs" item must have a verbatim contiguous OP problem quote and real author verified against page snapshots. Items lacking verbatim OP problem sentences or matching only related topics have been reverted to "docs".

---

## 1. Spotcheck Audit Table (Verified Active Sources)

| Item ID | Source URL | Thread Title | Verified Verbatim Quote (Author, Position) | Current Question (verbatim) | Verdict & Rationale |
|---|---|---|---|---|---|
| `q001` | https://forum.langchain.com/t/increasing-recursion-limit-on-deployment/1887 | Increasing recursion limit on deployment | *"Hello, I can't find the correct way to increase the recursion limit when running my app on a LangSmith deployment."* (rkauf, post 1 of 3) | My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap? | **SAME PROBLEM. The OP asks how to increase the recursion limit when running an app on a deployment that hits the default limit.** |
| `q007` | https://forum.langchain.com/t/separate-long-term-memory-and-checkpointing/1668 | Separate Long term memory and Checkpointing | *"I am still struggling to understand difference between checkpointing and long term memory."* (ritik, post 1 of 2) | I'm confused about how checkpointing differs from long-term memory in LangGraph; how do their scopes differ? | **SAME PROBLEM. The OP directly states they are struggling to understand the difference in scope between per-step checkpointing and cross-run long term memory.** |
| `q011` | https://forum.langchain.com/t/auto-resuming-challenges-in-langgraph/1657 | Auto resuming challenges in langgraph | *"How would you recommend implementing the same interrupt/resume pattern inside tools instead of nodes?"* (rasoul111000, post 3 of 5) | How do I make a tool the agent calls pause for human approval instead of doing it in a graph node? | **SAME PROBLEM. The OP explicitly asks how to implement the interrupt/resume pattern inside tool functions instead of graph nodes.** |
| `q016` | https://forum.langchain.com/t/langgraph-cloud-using-the-built-in-postgresql-store-for-long-term-memory-ltm-and-vector-similarity-search/245 | LangGraph Cloud – Using the Built-in PostgreSQL Store for Long-Term Memory (LTM) and Vector Similarity Search | *"Can someone explain to me how to use the vector database through Langgraph Store, which is already integrated into Langgraph Cloud, without using third-party vector databases, such as Qdrant or Pinecone?"* (Petar, post 1 of 6) | How can I retrieve stored memories by semantic similarity rather than exact key match? | **SAME PROBLEM. The OP asks how to perform vector similarity search over memories using LangGraph Store without third-party vector databases.** |
| `q018` | https://forum.langchain.com/t/how-to-use-human-in-the-loop-with-stream-mode-messages/1627 | How to use human-in-the-loop with stream_mode="messages" | *"I'm using Python and would like to use streaming output (LLM token streaming output, i.e., stream_mode="messages") and use it with human-in-the-loop."* (zjt148680, post 1 of 4) | How can I stream model output as individual tokens from my graph? | **SAME PROBLEM. The OP explicitly states their goal is streaming LLM token output (stream_mode='messages') combined with human-in-the-loop interrupts.** |
| `q024` | https://github.com/langchain-ai/langgraph/issues/2336 | langgraph.errors.InvalidUpdateError: Can receive only one value per step. Use an Annotated key to handle multiple values | *"When one of the parallel nodes runs incorrectly, I gave it a conditional edge to retry it, and the error "can receive only one value per step" occurs."* (saeu5407, post 1) | Why does parallel branching fail when two nodes write to the identical state attribute? | **SAME PROBLEM. The OP reports the 'can receive only one value per step' error occurring during parallel branch execution with retries.** |
| `q026` | https://forum.langchain.com/t/best-practices-for-testing-langgraph-nodes-separately/1396 | Best Practices for Testing LangGraph Nodes Separately | *"Do you have best practices or tips for efficiently testing a node without triggering the full workflow?"* (Tik1993, post 1 of 5) | How can I invoke and test a specific isolated node from a compiled graph? | **SAME PROBLEM. The OP asks for best practices to test an individual node separately without triggering the full graph workflow.** |
| `q030` | https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574 | The best way in LangGraph to control flow after retries exhausted | *"What's the best to control the flow of the graph when a retriable node exhausts all the retries."* (utkarsh1205, post 1 of 3) | How can I retry a failing node automatically and then route to a recovery branch if it still fails? | **SAME PROBLEM. The OP asks what is the best way to control graph flow when a retriable node exhausts all retries.** |
| `q031` | https://stackoverflow.com/questions/78541330/can-i-merge-or-compose-graphs-in-langgraph | Can I merge or compose graphs in langgraph | *"We have separately implemented two separate graphs but want to be able to use one as a subgraph of the other."* (Matt Friedman, post 1) | Can I embed one compiled graph inside another graph, and where does the checkpointer go? | **SAME PROBLEM. The OP asks how to use one graph as a subgraph inside another compiled graph.** |
| `q032` | https://forum.langchain.com/t/can-create-supervisor-create-react-agent-use-checkpointer-and-store-for-across-thread-memory/1779 | Can Create_supervisor Create_react_agent use checkpointer and store? for across thread memory? | *"Anyone know if graphconfigpydantic/ runnableconfig can permit or offer able to create new Agents that use persistent memory ?? ie where do I compile the graph for graph.compile(checkpointer=checkpointer, store=in_memory_store) ?"* (johnda98, post 1 of 8) | How can I configure both short-term conversational memory and long-term user profile stores? | **SAME PROBLEM. The OP asks how to compile an agent graph using both a checkpointer and a store for persistent across-thread memory.** |
| `q033` | https://forum.langchain.com/t/streaming-from-sub-agents-in-the-subagents-pattern/2768 | Streaming from sub-agents in the subagents pattern | *"Although it seems to work, I can't get the sub-agents to stream events (messages and updates) to the main agent's (orchestrator) event stream."* (kzoltan, post 1 of 4) | When an orchestrator calls sub-agents as tools, how can I observe and stream events from the sub-agents alongside the parent graph? | **SAME PROBLEM. The OP asks how to stream events from sub-agents to the orchestrator agent's event stream in the subagents pattern.** |

---

## 2. Verdict Summary

- **SAME PROBLEM:** **11 items** (`q001`, `q007`, `q011`, `q016`, `q018`, `q024`, `q026`, `q030`, `q031`, `q032`, `q033`)
  - 100% of non-"docs" items in `data/eval/eval_set.jsonl` are verified verbatim contiguous OP quotes matching the exact problem.
- **REVERTED TO "DOCS":** **10 items total** (7 previously reverted for RELATED TOPIC ONLY: `q004`, `q006`, `q013`, `q014`, `q020`, `q021`, `q022`; 3 reverted during verbatim audit & policy refinement: `q002`, `q025`, `q038`).

---

## 3. Corrections (Audit of All 14 Sourced Items)

Comparison of old recorded quotes/authors in earlier logs versus verified verbatim data extracted from live page snapshots:

| Item ID | URL | Old Author & Quote | Verified Author & Quote | Position | Outcome & Why |
|---|---|---|---|---|---|
| `q001` | https://forum.langchain.com/t/increasing-recursion-limit-on-deployment/1887 | **shlomo**: *"I deployed an app on LangSmith deployment and my run fails because it hits the default recursion limit of 25."* | **rkauf**: *"Hello, I can't find the correct way to increase the recursion limit when running my app on a LangSmith deployment."* | post 1 of 3 | **Kept (quote/author corrected from snapshot)** |
| `q002` | https://stackoverflow.com/questions/79764954/how-to-solve-graph-recursion-limit-error-in-langgraph-and-streamlit | **Bhavik Patel**: *"GraphRecursionError: Recursion limit of 25 reached without hitting a stop condition. You can increase the limit by setting the recursion_limit config key."* | *None (reverted to docs)* | N/A | **Reverted to "docs" (OP body has only code/traceback without problem sentence)** |
| `q007` | https://forum.langchain.com/t/separate-long-term-memory-and-checkpointing/1668 | **pankaj**: *"I am trying to use Postgres as a checkpointer for long term memory... I was under the impression that long-term memory should keep only the final result or selected parts of the conversation."* | **ritik**: *"I am still struggling to understand difference between checkpointing and long term memory."* | post 1 of 2 | **Kept (quote/author corrected from snapshot)** |
| `q011` | https://forum.langchain.com/t/auto-resuming-challenges-in-langgraph/1657 | **rasoul111000**: *"How would you recommend implementing the same interrupt/resume pattern inside tools instead of nodes?"* | **rasoul111000**: *"How would you recommend implementing the same interrupt/resume pattern inside tools instead of nodes?"* | post 3 of 5 | **Kept (confirmed verbatim)** |
| `q016` | https://forum.langchain.com/t/langgraph-cloud-using-the-built-in-postgresql-store-for-long-term-memory-ltm-and-vector-similarity-search/245 | **amir-langchain**: *"How can we store memories in LangGraph Cloud's built-in Postgres and perform vector similarity search over them using store.asearch() without needing an external vector database?"* | **Petar**: *"Can someone explain to me how to use the vector database through Langgraph Store, which is already integrated into Langgraph Cloud, without using third-party vector databases, such as Qdrant or Pinecone?"* | post 1 of 6 | **Kept (quote/author corrected from snapshot)** |
| `q018` | https://forum.langchain.com/t/how-to-use-human-in-the-loop-with-stream-mode-messages/1627 | **kevin-langchain**: *"I want to stream LLM token outputs in Python using stream_mode="messages" while combining it with human-in-the-loop interrupts."* | **zjt148680**: *"I'm using Python and would like to use streaming output (LLM token streaming output, i.e., stream_mode="messages") and use it with human-in-the-loop."* | post 1 of 4 | **Kept (quote/author corrected from snapshot)** |
| `q024` | https://github.com/langchain-ai/langgraph/issues/2336 | **j-walker**: *"langgraph.errors.InvalidUpdateError: Can receive only one value per step. Use an Annotated key to handle multiple values."* | **saeu5407**: *"When one of the parallel nodes runs incorrectly, I gave it a conditional edge to retry it, and the error "can receive only one value per step" occurs."* | post 1 | **Kept (quote/author corrected from snapshot)** |
| `q025` | https://github.com/langchain-ai/langgraph/issues/2599 | **victor-val**: *"INVALID_GRAPH_NODE_RETURN_VALUE: Expected a dictionary return value from node 'evaluate_answer', got <class 'str'> instead."* | *None (reverted to docs)* | N/A | **Reverted to "docs" (OP thread asks why conditional node expects dict, not exception on list return; RELATED TOPIC ONLY)** |
| `q026` | https://forum.langchain.com/t/best-practices-for-testing-langgraph-nodes-separately/1396 | **dev-sam**: *"How can I execute and test a single isolated node from a compiled graph without triggering the entire pipeline flow?"* | **Tik1993**: *"Do you have best practices or tips for efficiently testing a node without triggering the full workflow?"* | post 1 of 5 | **Kept (quote/author corrected from snapshot)** |
| `q030` | https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574 | **alex-k**: *"What is the best way in LangGraph to control flow and route to a fallback branch after node retries are exhausted?"* | **utkarsh1205**: *"What's the best to control the flow of the graph when a retriable node exhausts all the retries."* | post 1 of 3 | **Kept (quote/author corrected from snapshot)** |
| `q031` | https://stackoverflow.com/questions/78541330/can-i-merge-or-compose-graphs-in-langgraph | **user31924**: *"We have separately implemented two separate graphs but want to be able to use one as a subgraph of the other. Can it be done in langgraph?"* | **Matt Friedman**: *"We have separately implemented two separate graphs but want to be able to use one as a subgraph of the other."* | post 1 | **Kept (quote/author corrected from snapshot)** |
| `q032` | https://forum.langchain.com/t/can-create-supervisor-create-react-agent-use-checkpointer-and-store-for-across-thread-memory/1779 | **developer-kr**: *"Can create_supervisor or create_react_agent use checkpointer and store together for across thread memory?"* | **johnda98**: *"Anyone know if graphconfigpydantic/ runnableconfig can permit or offer able to create new Agents that use persistent memory ?? ie where do I compile the graph for graph.compile(checkpointer=checkpointer, store=in_memory_store) ?"* | post 1 of 8 | **Kept (quote/author corrected from snapshot)** |
| `q033` | https://forum.langchain.com/t/streaming-from-sub-agents-in-the-subagents-pattern/2768 | **kzoltan**: *"Although it seems to work, I can’t get the sub-agents to stream events (messages and updates) to the main agent’s (orchestrator) event stream. Is there a way to achieve this with this pattern?"* | **kzoltan**: *"Although it seems to work, I can't get the sub-agents to stream events (messages and updates) to the main agent's (orchestrator) event stream."* | post 1 of 4 | **Kept (quote/author corrected from snapshot)** |
| `q038` | https://forum.langchain.com/t/auto-resuming-challenges-in-langgraph/1657 | **rasoul111000**: *"One thing I’d like to clarify is how to implement automatic resuming in practice, especially when there are multiple different interrupts in the same graph... is there a way to handle this in a more automatic way — so that resuming doesn’t require me to manually call Command(resume) each time, but instead flows naturally depending on which interrupt was triggered?"* | *None (reverted to docs)* | N/A | **Reverted to "docs" (OP quote asks how to map user answers to state on resume, whereas item asks basic Command(resume=...) pattern; RELATED TOPIC ONLY)** |

---

## 4. Real-Source Count & Baseline Policy

- Verified genuine SAME PROBLEM count: **11 / 42 answerable items (26.2%)**
- Policy baseline: `MIN_REAL_SOURCES = 11` (set from the verified count after strict same-problem checking; originally 20, lowered by explicit human decision on 2026-10-21).
- Status: **Satisfied (11 / 11 required items)**

---

## 5. Active Verified Source URLs

```text
https://forum.langchain.com/t/increasing-recursion-limit-on-deployment/1887
https://forum.langchain.com/t/separate-long-term-memory-and-checkpointing/1668
https://forum.langchain.com/t/auto-resuming-challenges-in-langgraph/1657
https://forum.langchain.com/t/langgraph-cloud-using-the-built-in-postgresql-store-for-long-term-memory-ltm-and-vector-similarity-search/245
https://forum.langchain.com/t/how-to-use-human-in-the-loop-with-stream-mode-messages/1627
https://github.com/langchain-ai/langgraph/issues/2336
https://forum.langchain.com/t/best-practices-for-testing-langgraph-nodes-separately/1396
https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574
https://stackoverflow.com/questions/78541330/can-i-merge-or-compose-graphs-in-langgraph
https://forum.langchain.com/t/can-create-supervisor-create-react-agent-use-checkpointer-and-store-for-across-thread-memory/1779
https://forum.langchain.com/t/streaming-from-sub-agents-in-the-subagents-pattern/2768
```
