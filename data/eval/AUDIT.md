# Mechanical Evaluation Audit Report

## Summary Metrics
- Total Items Audited: 50 (Answerable: 42)
- Unresolved Evidence References: 0
- must_mention Failures (Evidence-Only): 0
- Reference-Answer Grounding Flags: 0
- Case-Insensitive 4-Gram Overlap Violations: 0
- Noisy Evidence Items (>3 chunks): 3 (q031, q032, q036)
- Version Items Proof Violations: 0
- Page Spread: 27 distinct pages (Max items per page: 5)

## Page Spread Distribution
| Document Path | Item Count |
|---|---|
| `checkpointers.mdx` | 5 |
| `fault-tolerance.mdx` | 5 |
| `stores.mdx` | 4 |
| `interrupts.mdx` | 3 |
| `functional-api.mdx` | 3 |
| `event-streaming.mdx` | 3 |
| `errors/GRAPH_RECURSION_LIMIT.mdx` | 2 |
| `graph-api.mdx` | 2 |
| `add-memory.mdx` | 2 |
| `errors/MISSING_CHECKPOINTER.mdx` | 1 |
| `persistence.mdx` | 1 |
| `agentic-rag.mdx` | 1 |
| `use-time-travel.mdx` | 1 |
| `streaming.mdx` | 1 |
| `local-server.mdx` | 1 |
| `application-structure.mdx` | 1 |
| `workflows-agents.mdx` | 1 |
| `backward-compatibility.mdx` | 1 |
| `errors/INVALID_CONCURRENT_GRAPH_UPDATE.mdx` | 1 |
| `errors/INVALID_GRAPH_NODE_RETURN_VALUE.mdx` | 1 |
| `test.mdx` | 1 |
| `studio.mdx` | 1 |
| `pregel.mdx` | 1 |
| `use-subgraphs.mdx` | 1 |
| `choosing-apis.mdx` | 1 |
| `sql-agent.mdx` | 1 |
| `thinking-in-langgraph.mdx` | 1 |

## Per-Item Audit Findings (Answerable Items)

### q001 [SINGLE]
**Question:** My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?

**Evidence Resolution:**
- `[RESOLVED]` `errors/GRAPH_RECURSION_LIMIT.mdx#troubleshooting` -> chunks: `['0b10c87050fe58d0']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (2 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q002 [SINGLE]
**Question:** What makes a compiled StateGraph stop with a recursion-limit error even though nothing seems broken?

**Evidence Resolution:**
- `[RESOLVED]` `errors/GRAPH_RECURSION_LIMIT.mdx#` -> chunks: `['96011abbfc237af0']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (0 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q003 [SINGLE]
**Question:** What do I change in compile() to fix the MISSING_CHECKPOINTER error?

**Evidence Resolution:**
- `[RESOLVED]` `errors/MISSING_CHECKPOINTER.mdx#troubleshooting` -> chunks: `['4c5a8d9f78149c8e']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (4 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q004 [SINGLE]
**Question:** How do I define a state key so new items append to a list instead of replacing it?

**Evidence Resolution:**
- `[RESOLVED]` `graph-api.mdx#reducers` -> chunks: `['ff0dadd65396e79d', '540b8fc8f2044f70', 'b26cfbd35ff7c0a0']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (3 chunks)

### q005 [SINGLE]
**Question:** Which virtual node identifier marks the initial entry transition in StateGraph?

**Evidence Resolution:**
- `[RESOLVED]` `graph-api.mdx#conditional-entry-point` -> chunks: `['dffc7ac3a4031636']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (3 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q006 [SINGLE]
**Question:** What method lets an operator overwrite state attributes on an existing thread without running a node?

**Evidence Resolution:**
- `[RESOLVED]` `checkpointers.mdx#update-state` -> chunks: `['39bfcdd6dee87c7d']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q007 [SINGLE]
**Question:** I'm confused about how checkpointing differs from long-term memory in LangGraph; how do their scopes differ?

**Evidence Resolution:**
- `[RESOLVED]` `persistence.mdx#checkpointer-vs-store` -> chunks: `['df2d3fc4dd1af2e9']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (0 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q008 [SINGLE]
**Question:** How can I retrieve the complete sequence of past checkpoints recorded for a specific conversation?

**Evidence Resolution:**
- `[RESOLVED]` `checkpointers.mdx#get-state-history` -> chunks: `['b5c18071f5857d79', '8cc8a801fc6f292c', '0964dcef782c7a63']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (2 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (3 chunks)

### q009 [VERSION]
**Question:** Which channel mechanism avoids storing redundant duplicate states by persisting only incremental changes?

**Evidence Resolution:**
- `[RESOLVED]` `checkpointers.mdx#optimize-checkpoint-storage` -> chunks: `['1275ba85560b4ff7']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

**Version Proof Status:** `[PASSED]` Documented proof with external release/docs URL

### q010 [SINGLE]
**Question:** How can a node see its current retry attempt number and the thread ID?

**Evidence Resolution:**
- `[RESOLVED]` `fault-tolerance.mdx#inspect-retry-state` -> chunks: `['6d61f021e1b376c4']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (3 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q011 [SINGLE]
**Question:** How do I make a tool the agent calls pause for human approval instead of doing it in a graph node?

**Evidence Resolution:**
- `[RESOLVED]` `interrupts.mdx#interrupts-in-tools` -> chunks: `['6ced6b386734272e', '061155e97a7ac1c1']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (0 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

### q012 [SINGLE]
**Question:** Which built-in state class gives me a messages list out of the box?

**Evidence Resolution:**
- `[RESOLVED]` `agentic-rag.mdx#generate-a-query-or-respond` -> chunks: `['ab776ed497604649']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q013 [SINGLE]
**Question:** How do I turn a plain Python function into a workflow that can be checkpointed and interrupted?

**Evidence Resolution:**
- `[RESOLVED]` `functional-api.mdx#example` -> chunks: `['4e87bf3df084938d', 'a0fccbb865ec2164']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

### q014 [SINGLE]
**Question:** Which decorator wraps individual discrete steps executed within an entrypoint workflow?

**Evidence Resolution:**
- `[RESOLVED]` `functional-api.mdx#example` -> chunks: `['4e87bf3df084938d', 'a0fccbb865ec2164']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

### q015 [SINGLE]
**Question:** How can I branch history starting from an earlier saved snapshot to evaluate an alternative flow?

**Evidence Resolution:**
- `[RESOLVED]` `use-time-travel.mdx#fork` -> chunks: `['bfcd78e39450d9bb']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (3 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q016 [SINGLE]
**Question:** How can I retrieve stored memories by semantic similarity rather than exact key match?

**Evidence Resolution:**
- `[RESOLVED]` `stores.mdx#semantic-search` -> chunks: `['cb8c508e1c265c7a']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q017 [SINGLE]
**Question:** What method saves key-value memory data into a hierarchical namespace in BaseStore?

**Evidence Resolution:**
- `[RESOLVED]` `stores.mdx#basic-usage` -> chunks: `['2bcb4281380ea615', '85128de843b4ae59']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

### q018 [SINGLE]
**Question:** How can I stream model output as individual tokens from my graph?

**Evidence Resolution:**
- `[RESOLVED]` `streaming.mdx#stream-modes` -> chunks: `['b0ad222fb82eb8ef']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q019 [SINGLE]
**Question:** How do you configure breakpoints to pause execution prior to running specified nodes?

**Evidence Resolution:**
- `[RESOLVED]` `interrupts.mdx#debugging-with-interrupts` -> chunks: `['31745a815bc93b7b', '7b03ff9dc6a71a13']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (2 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

### q020 [SINGLE]
**Question:** How do I spin up the local development service from the terminal?

**Evidence Resolution:**
- `[RESOLVED]` `local-server.mdx#5-launch-agent-server` -> chunks: `['9886d7a7d1975b69']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (2 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q021 [SINGLE]
**Question:** Which file configures a LangGraph app for deployment?

**Evidence Resolution:**
- `[RESOLVED]` `application-structure.mdx#` -> chunks: `['9d8be13faa62417c']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (2 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q022 [SINGLE]
**Question:** Which prebuilt node runs the tools an LLM requested?

**Evidence Resolution:**
- `[RESOLVED]` `workflows-agents.mdx#toolnode` -> chunks: `['4d77bbc1a5d58dd7']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q023 [SINGLE]
**Question:** How do you ensure state schema changes remain compatible with existing thread checkpoints?

**Evidence Resolution:**
- `[RESOLVED]` `backward-compatibility.mdx#recommended-patterns` -> chunks: `['68dc2c547ef50a2c']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q024 [SINGLE]
**Question:** Why does parallel branching fail when two nodes write to the identical state attribute?

**Evidence Resolution:**
- `[RESOLVED]` `errors/INVALID_CONCURRENT_GRAPH_UPDATE.mdx#` -> chunks: `['8938c817a4c2ce9a']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q025 [SINGLE]
**Question:** What exception is raised when a node function outputs a list rather than a mapping?

**Evidence Resolution:**
- `[RESOLVED]` `errors/INVALID_GRAPH_NODE_RETURN_VALUE.mdx#` -> chunks: `['7df8ede5a20eb979']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q026 [SINGLE]
**Question:** How can I invoke and test a specific isolated node from a compiled graph?

**Evidence Resolution:**
- `[RESOLVED]` `test.mdx#testing-individual-nodes-and-edges` -> chunks: `['ab8cf99857cfe02b']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q027 [SINGLE]
**Question:** Which tool lets me visually inspect each step of my agent locally?

**Evidence Resolution:**
- `[RESOLVED]` `studio.mdx#` -> chunks: `['eb1ae9d4f1d366fb']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q028 [SINGLE]
**Question:** In Pregel, which channel is used by default, and what happens to earlier values?

**Evidence Resolution:**
- `[RESOLVED]` `pregel.mdx#topic` -> chunks: `['b6245552f6a0196c']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

### q029 [MULTI]
**Question:** How do I set up a graph with SQLite persistence and resume an interrupted thread?

**Evidence Resolution:**
- `[RESOLVED]` `checkpointers.mdx#checkpointer-libraries` -> chunks: `['9efb6d35adcf1f17']`
- `[RESOLVED]` `event-streaming.mdx#resume-after-an-interrupt` -> chunks: `['f5fb04c45d975bc6']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (3 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

### q030 [MULTI]
**Question:** How can I retry a failing node automatically and then route to a recovery branch if it still fails?

**Evidence Resolution:**
- `[RESOLVED]` `fault-tolerance.mdx#error-handling` -> chunks: `['21cf6cebc6be0c62']`
- `[RESOLVED]` `fault-tolerance.mdx#route-with-command` -> chunks: `['05aae600ce109ffa']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (3 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

### q031 [MULTI]
**Question:** Can I embed one compiled graph inside another graph, and where does the checkpointer go?

**Evidence Resolution:**
- `[RESOLVED]` `add-memory.mdx#use-in-subgraphs` -> chunks: `['235b0bdf5e99602a']`
- `[RESOLVED]` `use-subgraphs.mdx#call-a-subgraph-inside-a-node` -> chunks: `['f7ae465ad3a0486c', 'b59fec0a6548c02b', '95e5678a6aff2964', 'a45b96a7faff4e9a', '014138ce682349c8']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (0 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** HIGH (6 chunks: `['235b0bdf5e99602a', 'f7ae465ad3a0486c', 'b59fec0a6548c02b', '95e5678a6aff2964', 'a45b96a7faff4e9a', '014138ce682349c8']`)

### q032 [MULTI]
**Question:** How can I configure both short-term conversational memory and long-term user profile stores?

**Evidence Resolution:**
- `[RESOLVED]` `add-memory.mdx#add-long-term-memory` -> chunks: `['8891e840c03d5443']`
- `[RESOLVED]` `stores.mdx#using-in-langgraph` -> chunks: `['bcadf7322547cf2e', 'f3e704dfdd7e2cda', '47a03fde39c98196']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** HIGH (4 chunks: `['8891e840c03d5443', 'bcadf7322547cf2e', 'f3e704dfdd7e2cda', '47a03fde39c98196']`)

### q033 [MULTI]
**Question:** When an orchestrator dispatches sub-agents through tools, how do I print the parent agent's own tokens and also follow each sub-agent's messages from a single streaming run?

**Evidence Resolution:**
- `[RESOLVED]` `event-streaming.mdx#quickstart` -> chunks: `['cc15c7cc538f0119']`
- `[RESOLVED]` `event-streaming.mdx#stream-subgraphs` -> chunks: `['2c6d8f38713f8d5d']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (5 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

### q034 [MULTI]
**Question:** How do I read the saved state of a thread and then edit it?

**Evidence Resolution:**
- `[RESOLVED]` `checkpointers.mdx#get-state` -> chunks: `['2661915e250cbc54', 'dfa40deca1c1011a']`
- `[RESOLVED]` `checkpointers.mdx#update-state` -> chunks: `['39bfcdd6dee87c7d']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (3 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (3 chunks)

### q035 [MULTI]
**Question:** What is required to migrate from a functional workflow into a full StateGraph definition?

**Evidence Resolution:**
- `[RESOLVED]` `functional-api.mdx#example` -> chunks: `['4e87bf3df084938d', 'a0fccbb865ec2164']`
- `[RESOLVED]` `choosing-apis.mdx#from-functional-to-graph-api` -> chunks: `['7ce044015429a1c0']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (5 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (3 chunks)

### q036 [MULTI]
**Question:** How can I build an agent that queries a database and stores summaries across conversations?

**Evidence Resolution:**
- `[RESOLVED]` `sql-agent.mdx#3-add-tools-for-database-interactions` -> chunks: `['13c4a6dc9b720c7f']`
- `[RESOLVED]` `stores.mdx#using-in-langgraph` -> chunks: `['bcadf7322547cf2e', 'f3e704dfdd7e2cda', '47a03fde39c98196']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (3 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** HIGH (4 chunks: `['13c4a6dc9b720c7f', 'bcadf7322547cf2e', 'f3e704dfdd7e2cda', '47a03fde39c98196']`)

### q037 [VERSION]
**Question:** How do I pause graph execution inside a node to wait for human approval?

**Evidence Resolution:**
- `[RESOLVED]` `interrupts.mdx#pause-using-interrupt` -> chunks: `['43d2773fee2c265d']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

**Version Proof Status:** `[PASSED]` Documented proof with external release/docs URL

### q038 [VERSION]
**Question:** How should a paused graph execution be resumed with user provided data?

**Evidence Resolution:**
- `[RESOLVED]` `event-streaming.mdx#resume-after-an-interrupt` -> chunks: `['f5fb04c45d975bc6']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (1 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

**Version Proof Status:** `[PASSED]` Documented proof with external release/docs URL

### q039 [SINGLE]
**Question:** How can a node dynamically decide which destination node to trigger next while updating state?

**Evidence Resolution:**
- `[RESOLVED]` `thinking-in-langgraph.mdx#handle-errors-appropriately` -> chunks: `['6a7f10d0ecdf12d8', 'c638ad2c8a69414b', '6a63b30c942eddb4']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (0 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (3 chunks)

### q040 [VERSION]
**Question:** How can I configure graph-wide retry and error handler defaults across all nodes?

**Evidence Resolution:**
- `[RESOLVED]` `fault-tolerance.mdx#graph-defaults` -> chunks: `['935b436334202a8a']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (5 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

**Version Proof Status:** `[PASSED]` Documented proof with external release/docs URL

### q041 [VERSION]
**Question:** How do I attach a dedicated error handler to a node when all retries fail?

**Evidence Resolution:**
- `[RESOLVED]` `fault-tolerance.mdx#error-handling` -> chunks: `['21cf6cebc6be0c62']`
- `[RESOLVED]` `fault-tolerance.mdx#nodeerror` -> chunks: `['d3cd6f2d08b06df8']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (3 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (2 chunks)

**Version Proof Status:** `[PASSED]` Documented proof with external release/docs URL

### q042 [VERSION]
**Question:** How do I place an execution time limit on an individual node attempt?

**Evidence Resolution:**
- `[RESOLVED]` `fault-tolerance.mdx#timeouts` -> chunks: `['124b7d2b637c8e75']`

**must_mention (Evidence-Only):** PASSED (All present in evidence chunks)

**Reference-Answer Grounding:** CLEAN (4 code tokens verified)

**4-Gram Overlap:** PASSED (Zero shared 4-grams)

**Evidence Noise:** OK (1 chunks)

**Version Proof Status:** `[PASSED]` Documented proof with external release/docs URL
