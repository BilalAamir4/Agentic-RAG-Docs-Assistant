---
title: Guide to Graphs
---

import SomeComponent from '/snippets/comp.mdx';

This is the introduction to the guide explaining graph-based agents, workflows, and stateful architectures in LangGraph.

:::python
```python
def intro_func():
    return "python_only"
```
:::

:::js
```javascript
function introFunc() {
    return "js_only";
}
```
:::

## Core Principles

Short description of principles.

### Principle One

This is a tiny section under 80 tokens. It should be merged into the following section with the same parent heading.

### Principle Two

Here is the detailed second principle explaining workflow orchestration across multi-turn interactions.
Graphs model computations as vertices representing discrete units of work and edges representing transitions between states.
By structuring logic into isolated steps, applications gain fine-grained auditability and control over execution flows.
State transitions are fully deterministic while individual nodes may invoke stochastic large language model completions.
This separation allows engineering teams to enforce structural invariants without sacrificing generative flexibility.
Checkpointers capture graph snapshots after every node execution, enabling seamless recovery and time travel.

### Principle Three

A third principle highlighting human-in-the-loop capabilities, dynamic breakpoints, and explicit approval gates.
Human interventions allow operators to review proposed actions before execution occurs in sensitive operational environments.
By interrupting runs at designated nodes, developers build interactive systems that pause safely without losing thread context.

## Advanced Graph Execution

Here is the first long paragraph of the advanced execution section discussing execution order, channel synchronization, message reduction, and state updates across complex graph topologies. This paragraph introduces why checkpointing is essential for failure recovery and state inspection during complex multistep runs. Checkpointing writes intermediate state snapshots to durable databases such as PostgreSQL or SQLite, guaranteeing that long-running operations survive process terminations and unexpected infrastructure disruptions.

Here is a second paragraph that continues the discussion on checkpointing durability, database write operations, thread management, transaction isolation, and asynchronous workers. It explains the subtleties of persisting snapshots without blocking event loops during streaming executions. As nodes produce partial token streams, the underlying engine coordinates state channel merges with zero-copy efficiency. When errors occur, retry policies and fallback edges redirect traffic gracefully to alternative nodes.

Here is a third paragraph explaining time travel, replaying past states, editing messages before resumption, fork graphs, and debugging cyclic workflows. This paragraph completes the extended section text so that total tokens comfortably exceed 450 tokens across these three distinct paragraphs. By supplying a target checkpoint identifier, a user can rewind the conversation thread to an earlier state and branch into a new execution trajectory with altered parameters or state attributes.

Here is a fourth extensive paragraph discussing subgraphs, nested state architectures, communication protocols across hierarchical graphs, and distributed agentic orchestrations. Complex autonomous agents frequently divide responsibilities among specialized subagents, where each child graph possesses private state schemas and isolated reducer functions.

```python
# Large indivisible code fence that must never be split
def run_advanced_graph(app, initial_state):
    config = {"configurable": {"thread_id": "thread-123"}}
    for event in app.stream(initial_state, config=config):
        for node_name, state_update in event.items():
            print(f"Node {node_name} emitted update: {state_update}")
    return app.get_state(config)
```
