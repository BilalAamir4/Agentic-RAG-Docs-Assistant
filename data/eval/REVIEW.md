# Evaluation Dataset Human Review Sheet

Instructions for reviewer:
1. Check that each answer is factual, concise, and supported by documentation.
2. Check that question does not copy phrasing from evidence chunks.
3. For version questions, check that modern and outdated patterns are accurate.
4. For unanswerable questions, verify that keyword searches confirm absence.
5. Once reviewed and corrected, mark `[x] verified` and record any notes.

---

## [q001] My agent run stops with GRAPH_RECURSION_LIMIT; where do I set a bigger step cap?

- **Category:** `single`
- **Source:** https://forum.langchain.com/t/increasing-recursion-limit-on-deployment/1887
- **Must mention:** `recursion_limit`
- **Reference Answer:** Pass a higher recursion_limit in the config object when invoking the graph, e.g. graph.invoke(inputs, {"recursion_limit": 1000}).

### Evidence Chunks

#### Chunk `0b10c87050fe58d0` (https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT#troubleshooting)
**Doc Path:** `errors/GRAPH_RECURSION_LIMIT.mdx` | **Anchor:** `troubleshooting`

```text
* If you are not expecting your graph to go through many iterations, you likely have a cycle. Check your logic for infinite loops.

* If you have a complex graph, you can pass in a higher `recursion_limit` value into your `config` object when invoking your graph like this:

```python
graph.invoke({...}, {"recursion_limit": 1000})
```
```

[ ] verified
Reviewer note:

---

## [q002] What makes a compiled StateGraph stop with a recursion-limit error even though nothing seems broken?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `StateGraph`
- **Reference Answer:** The graph reached the maximum number of steps before hitting a stop condition. This is often an infinite loop from a cycle (e.g. edges a->b and b->a), but complex graphs can also hit the default limit naturally.

### Evidence Chunks

#### Chunk `96011abbfc237af0` (https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT)
**Doc Path:** `errors/GRAPH_RECURSION_LIMIT.mdx` | **Anchor:** ``

```text
Your LangGraph @[`StateGraph`] reached the maximum number of steps before hitting a stop condition.
This is often due to an infinite loop caused by code like the example below:

```python
from typing import TypedDict

from langgraph.graph import StateGraph

class State(TypedDict):
    some_key: str

builder = StateGraph(State)
builder.add_node("a", ...)
builder.add_node("b", ...)
builder.add_edge("a", "b")
builder.add_edge("b", "a")
...

graph = builder.compile()
```


However, complex graphs may hit the default limit naturally.
```

[ ] verified
Reviewer note:

---

## [q003] What do I change in compile() to fix the MISSING_CHECKPOINTER error?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `checkpointer`
- **Reference Answer:** Initialize a checkpointer (e.g. InMemorySaver) and pass it to compile() of the StateGraph, or to @entrypoint for the Functional API.

### Evidence Chunks

#### Chunk `4c5a8d9f78149c8e` (https://docs.langchain.com/oss/python/langgraph/errors/MISSING_CHECKPOINTER#troubleshooting)
**Doc Path:** `errors/MISSING_CHECKPOINTER.mdx` | **Anchor:** `troubleshooting`

```text
You are attempting to use built-in LangGraph persistence without providing a checkpointer.

This happens when a `checkpointer` is missing in the `compile()` method of @[`StateGraph`][StateGraph] or @[`@entrypoint`].

The following may help resolve this error:

-   Initialize and pass a checkpointer to the `compile()` method of @[`StateGraph`][StateGraph] or @[`@entrypoint`].


```python
from langgraph.checkpoint.memory import InMemorySaver
checkpointer = InMemorySaver()

# Graph API
from langgraph.graph import StateGraph
graph = StateGraph(...).compile(checkpointer=checkpointer)

# Functional API
from langgraph.func import entrypoint
@entrypoint(checkpointer=checkpointer)
def workflow(messages: list[str]) -> str:
    ...
```



-   Use the LangGraph API so you don't need to implement or configure checkpointers manually. The API handles all persistence infrastructure for you.

- Read more about persistence.
```

[ ] verified
Reviewer note:

---

## [q004] How do I define a state key so new items append to a list instead of replacing it?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `Annotated`, `operator.add`
- **Reference Answer:** Annotate the key with a reducer using Annotated, e.g. Annotated[list, operator.add]; without a reducer, updates overwrite the value.

### Evidence Chunks

#### Chunk `ff0dadd65396e79d` (https://docs.langchain.com/oss/python/langgraph/graph-api#reducers)
**Doc Path:** `graph-api.mdx` | **Anchor:** `reducers`

```text
Reducers are key to understanding how updates from nodes are applied to the `State`. Each key in the `State` has its own independent reducer function. If no reducer function is explicitly specified then it is assumed that all updates to that key should override it. There are a few different types of reducers, starting with the default type of reducer:

#### Reducer arguments

Every reducer is a binary function with two positional arguments:

- **Left argument**: The current value already stored in state for that key.
- **Right argument**: The update for that key returned by a node.

When a node returns a partial update, LangGraph calls the reducer for each updated key and saves the return value as the new state value:

```python
new_value = reducer(left=current_state[key], right=node_update[key])
```

The left argument always comes from accumulated state. The right argument always comes from the latest node update. The following example names both arguments explicitly:

Suppose the state is `{"tags": ["draft"]}` and a node returns `{"tags": ["review"]}`. LangGraph calls:

The new state value for `tags` is `["draft", "review"]`.

Custom reducers combine the left and right arguments. The default reducer discards the left argument and keeps only the right.

#### Default reducer

The default reducer ignores the left argument and replaces the state value with the right argument. This example shows how to use the default reducer:

In this example, no reducer functions are specified for any key. Let's assume the input to the graph is:
```

#### Chunk `540b8fc8f2044f70` (https://docs.langchain.com/oss/python/langgraph/graph-api#reducers)
**Doc Path:** `graph-api.mdx` | **Anchor:** `reducers`

```text
`{"foo": 1, "bar": ["hi"]}`. Let's then assume the first `Node` returns `{"foo": 2}`. This is treated as an update to the state. Notice that the `Node` does not need to return the whole `State` schema - just an update. After applying this update, the `State` would then be `{"foo": 2, "bar": ["hi"]}`. If the second node returns `{"bar": ["bye"]}` then the `State` would then be `{"foo": 2, "bar": ["bye"]}`

#### Custom reducers

A custom reducer combines the left and right arguments instead of replacing the state value, which is useful for accumulating values, such as appending updates to a list. This example shows how to specify a custom reducer:

In this example, we've used the `Annotated` type to specify a reducer function (`operator.add`) for the second key (`bar`). Note that the first key remains unchanged. Let's assume the input to the graph is `{"foo": 1, "bar": ["hi"]}`. Let's then assume the first `Node` returns `{"foo": 2}`. This is treated as an update to the state. Notice that the `Node` does not need to return the whole `State` schema - just an update. After applying this update, the `State` would then be `{"foo": 2, "bar": ["hi"]}`. If the second node returns `{"bar": ["bye"]}` then the `State` would then be `{"foo": 2, "bar": ["hi", "bye"]}`. Notice here that the `bar` key is updated by adding the two lists together.

#### Overwrite

In some cases, you may want to bypass a reducer and directly overwrite a state value. LangGraph provides the `Overwrite` type for this purpose. Learn how to use `Overwrite` here.

#### Resetting a reducer field
```

#### Chunk `b26cfbd35ff7c0a0` (https://docs.langchain.com/oss/python/langgraph/graph-api#reducers)
**Doc Path:** `graph-api.mdx` | **Anchor:** `reducers`

```text
A common source of confusion with reducers: with a merging reducer, returning an empty value does **not** clear the field. Because the reducer merges the right argument into the left one, an empty update is merged in and previously accumulated values are kept.

This pattern matters for error buffers or retry counters that must be cleared between retry attempts:

To clear the field while keeping a merging reducer, wrap the update with `Overwrite`:

For more information, see Bypass reducers with Overwrite.
```

[ ] verified
Reviewer note:

---

## [q005] Which virtual node identifier marks the initial entry transition in StateGraph?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `START`
- **Reference Answer:** The virtual START node: add an edge from START to the first node (graph.add_edge(START, "node_a")).

### Evidence Chunks

#### Chunk `dffc7ac3a4031636` (https://docs.langchain.com/oss/python/langgraph/graph-api#conditional-entry-point)
**Doc Path:** `graph-api.mdx` | **Anchor:** `conditional-entry-point`

```text
The entry point is the first node(s) that are run when the graph starts. You can use the @[`add_edge`] method from the virtual @[`START`][START] node to the first node to execute to specify where to enter the graph.

```python
from langgraph.graph import START

graph.add_edge(START, "node_a")
```

A conditional entry point lets you start at different nodes depending on custom logic. You can use @[`add_conditional_edges`] from the virtual @[`START`] node to accomplish this.

```python
from langgraph.graph import START

graph.add_conditional_edges(START, routing_function)
```

You can optionally provide a dictionary that maps the `routing_function`'s output to the name of the next node.

```python
graph.add_conditional_edges(START, routing_function, {True: "node_b", False: "node_c"})
```
```

[ ] verified
Reviewer note:

---

## [q006] What method lets an operator overwrite state attributes on an existing thread without running a node?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `update_state`
- **Reference Answer:** Call update_state(config, values). It creates a new checkpoint (the original is not modified) and passes values through reducers like a node update.

### Evidence Chunks

#### Chunk `39bfcdd6dee87c7d` (https://docs.langchain.com/oss/python/langgraph/checkpointers#update-state)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `update-state`

```text
You can edit the graph state using @`update_state`]. This creates a new checkpoint with the updated values — it does not modify the original checkpoint. The update is treated the same as a node update: values are passed through [reducer functions when defined, so channels with reducers _accumulate_ values rather than overwrite them.

You can optionally specify `as_node` to control which node the update is treated as coming from, which affects which node executes next. See Time travel: `as_node` for details.
```

[ ] verified
Reviewer note:

---

## [q007] I'm confused about how checkpointing differs from long-term memory in LangGraph; how do their scopes differ?

- **Category:** `single`
- **Source:** https://forum.langchain.com/t/separate-long-term-memory-and-checkpointing/1668
- **Must mention:** `Checkpointer`, `Store`
- **Reference Answer:** A checkpointer persists graph state snapshots scoped to a single thread (short-term memory); a store persists application-defined key-value data across threads (long-term memory).

### Evidence Chunks

#### Chunk `df2d3fc4dd1af2e9` (https://docs.langchain.com/oss/python/langgraph/persistence#checkpointer-vs-store)
**Doc Path:** `persistence.mdx` | **Anchor:** `checkpointer-vs-store`

```text
| | Checkpointer | Store |
| ---- | ---- | ---- |
| Persists | Graph state snapshots | Application-defined key-value data |
| Scope | A single thread | Across threads |
| Memory type | Short-term, thread-scoped memory | Long-term, cross-thread memory |
| Use for | Conversation continuity, human-in-the-loop, time travel, and fault tolerance | User preferences, facts, and shared knowledge |
| Access pattern | Pass a `thread_id` in graph config | Read and write items from nodes or application code |
| Full guide | Checkpointers | Stores |
```

[ ] verified
Reviewer note:

---

## [q008] How can I retrieve the complete sequence of past checkpoints recorded for a specific conversation?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `get_state_history`
- **Reference Answer:** Call graph.get_state_history(config) with the thread's config; it returns StateSnapshot objects ordered chronologically with the most recent first.

### Evidence Chunks

#### Chunk `b5c18071f5857d79` (https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state-history)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `get-state-history`

```text
You can get the full history of the graph execution for a given thread by calling @[`graph.get_state_history(config)`][get_state_history]. This will return a list of `StateSnapshot` objects associated with the thread ID provided in the config. Importantly, the checkpoints will be ordered chronologically with the most recent checkpoint / `StateSnapshot` being the first in the list.

```python
config = {"configurable": {"thread_id": "1"}}
list(graph.get_state_history(config))
```

In this example, the output of @[`get_state_history`] will look like this:
```

#### Chunk `8cc8a801fc6f292c` (https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state-history)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `get-state-history`

```text
```
[
    StateSnapshot(
        values={'foo': 'b', 'bar': ['a', 'b']},
        next=(),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28fe-6528-8002-5a559208592c'}},
        metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b', 'bar': ['b']}}, 'step': 2},
        created_at='2024-08-29T19:19:38.821749+00:00',
        parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f9-6ec4-8001-31981c2c39f8'}},
        tasks=(),
    ),
    StateSnapshot(
        values={'foo': 'a', 'bar': ['a']},
        next=('node_b',),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f9-6ec4-8001-31981c2c39f8'}},
        metadata={'source': 'loop', 'writes': {'node_a': {'foo': 'a', 'bar': ['a']}}, 'step': 1},
        created_at='2024-08-29T19:19:38.819946+00:00',
        parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f4-6b4a-8000-ca575a13d36a'}},
        tasks=(PregelTask(id='6fb7314f-f114-5413-a1f3-d37dfe98ff44', name='node_b', error=None, interrupts=()),),
    ),
    StateSnapshot(
        values={'foo': '', 'bar': []},
        next=('node_a',),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f4-6b4a-8000-ca575a13d36a'}},
        metadata={'source': 'loop', 'writes': None, 'step': 0},
        created_at='2024-08-29T19:19:38.817813+00:00',
        parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f0-6c66-bfff-6723431e8481'}},
        tasks=(PregelTask(id='f1b14528-5ee5-579c-949b-23ef9bfbed58', name='node_a', error=None, interrupts=()),),
    ),
    StateSnapshot(
        values={'bar': []},
        next=('__start__',),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f0-6c66-bfff-6723431e8481'}},
        metadata={'source': 'input', 'writes': {'foo': ''}, 'step': -1},
        created_at='2024-08-29T19:19:38.816205+00:00',
        parent_config=None,
        tasks=(PregelTask(id='6d27aa2e-d72b-5504-a36f-8620e54a76dd', name='__start__', error=None, interrupts=()),),
    )
]
```
```

#### Chunk `0964dcef782c7a63` (https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state-history)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `get-state-history`

```text
#### Find a specific checkpoint

You can filter the state history to find checkpoints matching specific criteria:

```python
history = list(graph.get_state_history(config))

# Find the checkpoint before a specific node executed
before_node_b = next(s for s in history if s.next == ("node_b",))

# Find a checkpoint by step number
step_2 = next(s for s in history if s.metadata["step"] == 2)

# Find checkpoints created by update_state
forks = [s for s in history if s.metadata["source"] == "update"]

# Find the checkpoint where an interrupt occurred
interrupted = next(
    s for s in history
    if s.tasks and any(t.interrupts for t in s.tasks)
)
```
```

[ ] verified
Reviewer note:

---

## [q009] Which channel mechanism avoids storing redundant duplicate states by persisting only incremental changes?

- **Category:** `version`
- **Source:** docs
- **Must mention:** `DeltaChannel`
- **Reference Answer:** DeltaChannel stores only incremental deltas instead of the full accumulated value, reducing checkpoint size for append-heavy channels. It requires langgraph>=1.2 and is in beta.
- **Notes:** Before langgraph 1.2, checkpoints wrote the full value of every state channel at each super-step; DeltaChannel is documented as requiring langgraph>=1.2 (beta). Proof: https://github.com/langchain-ai/langgraph/releases/tag/1.2.0 (release notes include DeltaChannel beta marking, #7732).

### Evidence Chunks

#### Chunk `1275ba85560b4ff7` (https://docs.langchain.com/oss/python/langgraph/checkpointers#optimize-checkpoint-storage)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `optimize-checkpoint-storage`

```text
By default, LangGraph checkpoints write the full value of every state channel at each super-step. For long-running threads with large accumulations—such as multi-turn conversations—this can produce significant storage growth over time.

@`DeltaChannel`] stores only incremental deltas instead of the full accumulated value, substantially reducing checkpoint size for append-heavy channels. See [DeltaChannel for usage and the storage-vs-latency tradeoff.


`DeltaChannel` requires `langgraph>=1.2` and is currently in beta. The API may change in future releases.
```

[ ] verified
Reviewer note:

---

## [q010] How can a node see its current retry attempt number and the thread ID?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `execution_info`, `node_attempt`
- **Reference Answer:** Declare a runtime: Runtime parameter on the node and read runtime.execution_info, e.g. node_attempt (1-indexed) and thread_id.

### Evidence Chunks

#### Chunk `6d61f021e1b376c4` (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#inspect-retry-state)
**Doc Path:** `fault-tolerance.mdx` | **Anchor:** `inspect-retry-state`

```text
Use execution info inside a node to inspect the current attempt number. This is useful for switching to a fallback when the primary call keeps failing:

```python
from langgraph.graph import StateGraph, START, END
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy
from typing_extensions import TypedDict

class State(TypedDict):
    result: str

def my_node(state: State, runtime: Runtime) -> State:
    if runtime.execution_info.node_attempt > 1:  # [!code highlight]
        return {"result": call_fallback_api()}
    return {"result": call_primary_api()}

builder = StateGraph(State)
builder.add_node("my_node", my_node, retry_policy=RetryPolicy(max_attempts=3))
builder.add_edge(START, "my_node")
builder.add_edge("my_node", END)
```

`execution_info` exposes the following fields:

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `node_attempt` | `int` | Current attempt number (1-indexed). `1` on the first try, `2` on the first retry, etc. |
| `node_first_attempt_time` | `float \| None` | Unix timestamp of when the first attempt started. Constant across retries. |
| `thread_id` | `str \| None` | Thread ID for the current execution. `None` without a checkpointer. |
| `run_id` | `str \| None` | Run ID for the current execution. `None` when not provided in config. |
| `checkpoint_id` | `str` | Checkpoint ID for the current execution. |
| `task_id` | `str` | Task ID for the current execution. |

`execution_info` is available even without a retry policy—`node_attempt` defaults to `1`.
```

[ ] verified
Reviewer note:

---

## [q011] How do I make a tool the agent calls pause for human approval instead of doing it in a graph node?

- **Category:** `single`
- **Source:** https://forum.langchain.com/t/auto-resuming-challenges-in-langgraph/1657
- **Must mention:** `interrupt`
- **Reference Answer:** Call interrupt() inside the tool function; resume execution with Command(resume=...), whose value becomes the return value of interrupt().

### Evidence Chunks

#### Chunk `6ced6b386734272e` (https://docs.langchain.com/oss/python/langgraph/interrupts#interrupts-in-tools)
**Doc Path:** `interrupts.mdx` | **Anchor:** `interrupts-in-tools`

```text
You can also place interrupts directly inside tool functions. This makes the tool itself pause for approval whenever it's called, and allows for human review and editing of the tool call before it is executed.

First, define a tool that uses @[`interrupt`]:

```python
from langchain.tools import tool
from langgraph.types import interrupt

@tool
def send_email(to: str, subject: str, body: str):
    """Send an email to a recipient."""

    # Pause before sending; payload surfaces on stream.interrupts when using event streaming
    response = interrupt({
        "action": "send_email",
        "to": to,
        "subject": subject,
        "body": body,
        "message": "Approve sending this email?"
    })

    if response.get("action") == "approve":
        # Resume value can override inputs before executing
        final_to = response.get("to", to)
        final_subject = response.get("subject", subject)
        final_body = response.get("body", body)
        return f"Email sent to {final_to} with subject '{final_subject}'"
    return "Email cancelled by user"
```

This approach is useful when you want the approval logic to live with the tool itself, making it reusable across different parts of your graph. The LLM can call the tool naturally, and the interrupt will pause execution whenever the tool is invoked, allowing you to approve, edit, or cancel the action.
```

#### Chunk `061155e97a7ac1c1` (https://docs.langchain.com/oss/python/langgraph/interrupts#interrupts-in-tools)
**Doc Path:** `interrupts.mdx` | **Anchor:** `interrupts-in-tools`

```text
```python
    import sqlite3
    import operator
    from typing import TypedDict, Annotated, Literal
    from langchain.tools import tool
    from langchain_anthropic import ChatAnthropic
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import Command, interrupt
    from langchain.messages import AnyMessage, SystemMessage, ToolMessage


    class AgentState(TypedDict):
        messages: Annotated[list[AnyMessage], operator.add]


    @tool
    def send_email(to: str, subject: str, body: str):
        """Send an email to a recipient."""

        # Pause before sending; payload surfaces on stream.interrupts when using event streaming
        response = interrupt({
            "action": "send_email",
            "to": to,
            "subject": subject,
            "body": body,
            "message": "Approve sending this email?",
        })

        if response.get("action") == "approve":
            final_to = response.get("to", to)
            final_subject = response.get("subject", subject)
            final_body = response.get("body", body)

            # Actually send the email (your implementation here)
            print(f"[send_email] to={final_to} subject={final_subject} body={final_body}")
            return f"Email sent to {final_to}"

        return "Email cancelled by user"


    model = ChatAnthropic(model="claude-sonnet-4-6").bind_tools([send_email])
    tools_by_name = {"send_email": send_email}


    def agent_node(state: AgentState):
        # LLM may decide to call the tool; interrupt pauses before sending
        result = model.invoke(state["messages"])
        return {"messages": [result]}

    def tool_node(state: AgentState):
        """Performs the tool call"""
        result = []
        for tool_call in state["messages"][-1].tool_calls:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
        return {"messages": result}

    def should_continue(state: AgentState) -> Literal["tool_node", END]:
        """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""
        messages = state["messages"]
        last_message = messages[-1]

        if last_message.tool_calls:
            return "tool_node"
        return END

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tool_node", tool_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, ["tool_node", END])  # Routes to "tools" or END
    builder.add_edge("tool_node", "agent")  # Loop back after tools

    checkpointer = SqliteSaver(
        sqlite3.connect("tool-approval.db", check_same_thread=False)
    )
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "email-workflow"}}
    initial = graph.stream_events(
        {
            "messages": [
                {"role": "user", "content": "Send an email to alice@example.com about the meeting"}
            ]
        },
        config=config,
        version="v3",
    )
    initial.output  # drive the stream to completion
    print(initial.interrupts)  # -> (Interrupt(value={'action': 'send_email', ...}),)

    # Resume with approval and optionally edited arguments
    resumed = graph.stream_events(
        Command(resume={"action": "approve", "subject": "Updated subject"}),
        config=config,
        version="v3",
    )
    print(resumed.output["messages"][-1])  # -> Tool result returned by send_email
    ```
```

[ ] verified
Reviewer note:

---

## [q012] Which built-in state class gives me a messages list out of the box?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `MessagesState`
- **Reference Answer:** MessagesState, which stores a messages list of chat messages.

### Evidence Chunks

#### Chunk `ab776ed497604649` (https://docs.langchain.com/oss/python/langgraph/agentic-rag#generate-a-query-or-respond)
**Doc Path:** `agentic-rag.mdx` | **Anchor:** `generate-a-query-or-respond`

```text
With the retriever tool ready, start building the agent as a LangGraph graph. In the Graph API, a graph is made of:

- **State**: Shared data that nodes read and update. This tutorial uses `MessagesState`, which stores a `messages` list of chat messages.


- **Nodes**: Functions that take the current state, run a step (for example, call a model or a tool), and return state updates.
- **Edges**: Connections that define which node runs next, including conditional edges that branch based on the state.

The first node is the agent decision point. Given the conversation so far, the model either answers the user directly or calls the retriever tool when the question needs blog context. That choice is what makes the system agentic rather than a fixed retrieve-then-generate pipeline: retrieval runs only when the model requests it.




Build a `generate_query_or_respond` node that calls the model on the current messages and binds the `retriever_tool` with `.bind_tools`:








**Output:**

```text wrap
================================== Ai Message ==================================

Hello! How can I help you today?
```




Ask a question that requires semantic search:



**Output:**

```text wrap
================================== Ai Message ==================================
Tool Calls:
retrieve_blog_posts (call_tYQxgfIlnQUDMdtAhdbXNwIM)
Call ID: call_tYQxgfIlnQUDMdtAhdbXNwIM
Args:
    query: types of reward hacking
```
```

[ ] verified
Reviewer note:

---

## [q013] How do I turn a plain Python function into a workflow that can be checkpointed and interrupted?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `entrypoint`
- **Reference Answer:** Decorate the function with @entrypoint (optionally with a checkpointer); it manages execution flow, long-running tasks and interrupts.

### Evidence Chunks

#### Chunk `4e87bf3df084938d` (https://docs.langchain.com/oss/python/langgraph/functional-api#example)
**Doc Path:** `functional-api.mdx` | **Anchor:** `example`

```text
Below we demonstrate a simple application that writes an essay and interrupts to request human review.

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import interrupt

@task
def write_essay(topic: str) -> str:
    """Write an essay about the given topic."""
    time.sleep(1) # A placeholder for a long-running task.
    return f"An essay about topic: {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> dict:
    """A simple workflow that writes an essay and asks for a review."""
    essay = write_essay("cat").result()
    is_approved = interrupt({
        # Any json-serializable payload provided to interrupt as argument.
        # It will be surfaced on the client side as an Interrupt when streaming data
        # from the workflow.
        "essay": essay, # The essay we want reviewed.
        # We can add any additional information that we need.
        # For example, introduce a key called "action" with some instructions.
        "action": "Please approve/reject the essay",
    })

    return {
        "essay": essay, # The essay that was generated
        "is_approved": is_approved, # Response from HIL
    }
```

This workflow will write an essay about the topic "cat" and then pause to get a review from a human. The workflow can be interrupted for an indefinite amount of time until a review is provided.

When the workflow is resumed, it executes from the very start, but because the result of the `writeEssay` task was already saved, the task result will be loaded from the checkpoint instead of being recomputed.

An essay has been written and is ready for review. Once the review is provided, we can resume the workflow:
```

#### Chunk `a0fccbb865ec2164` (https://docs.langchain.com/oss/python/langgraph/functional-api#example)
**Doc Path:** `functional-api.mdx` | **Anchor:** `example`

```text
The workflow has been completed and the review has been added to the essay.

The @`@entrypoint`] decorator can be used to create a workflow from a function. It encapsulates workflow logic and manages execution flow, including handling _long-running tasks_ and [interrupts.
```

[ ] verified
Reviewer note:

---

## [q014] Which decorator wraps individual discrete steps executed within an entrypoint workflow?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `@task`
- **Reference Answer:** @task; call the task and use .result() to get its value inside the entrypoint.

### Evidence Chunks

#### Chunk `4e87bf3df084938d` (https://docs.langchain.com/oss/python/langgraph/functional-api#example)
**Doc Path:** `functional-api.mdx` | **Anchor:** `example`

```text
Below we demonstrate a simple application that writes an essay and interrupts to request human review.

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import interrupt

@task
def write_essay(topic: str) -> str:
    """Write an essay about the given topic."""
    time.sleep(1) # A placeholder for a long-running task.
    return f"An essay about topic: {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> dict:
    """A simple workflow that writes an essay and asks for a review."""
    essay = write_essay("cat").result()
    is_approved = interrupt({
        # Any json-serializable payload provided to interrupt as argument.
        # It will be surfaced on the client side as an Interrupt when streaming data
        # from the workflow.
        "essay": essay, # The essay we want reviewed.
        # We can add any additional information that we need.
        # For example, introduce a key called "action" with some instructions.
        "action": "Please approve/reject the essay",
    })

    return {
        "essay": essay, # The essay that was generated
        "is_approved": is_approved, # Response from HIL
    }
```

This workflow will write an essay about the topic "cat" and then pause to get a review from a human. The workflow can be interrupted for an indefinite amount of time until a review is provided.

When the workflow is resumed, it executes from the very start, but because the result of the `writeEssay` task was already saved, the task result will be loaded from the checkpoint instead of being recomputed.

An essay has been written and is ready for review. Once the review is provided, we can resume the workflow:
```

#### Chunk `a0fccbb865ec2164` (https://docs.langchain.com/oss/python/langgraph/functional-api#example)
**Doc Path:** `functional-api.mdx` | **Anchor:** `example`

```text
The workflow has been completed and the review has been added to the essay.

The @`@entrypoint`] decorator can be used to create a workflow from a function. It encapsulates workflow logic and manages execution flow, including handling _long-running tasks_ and [interrupts.
```

[ ] verified
Reviewer note:

---

## [q015] How can I branch history starting from an earlier saved snapshot to evaluate an alternative flow?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `fork`, `update_state`
- **Reference Answer:** Fork: find a past checkpoint (via get_state_history), call update_state on that checkpoint's config with modified values to create a new branch, then invoke(None, fork_config) to continue. The original history stays intact.

### Evidence Chunks

#### Chunk `bfcd78e39450d9bb` (https://docs.langchain.com/oss/python/langgraph/use-time-travel#fork)
**Doc Path:** `use-time-travel.mdx` | **Anchor:** `fork`

```text
Fork creates a new branch from a past checkpoint with modified state. Call @[`update_state`] on a prior checkpoint to create the fork, then @[`invoke`][CompiledStateGraph.invoke] with `None` to continue execution.





`update_state` does **not** roll back a thread. It creates a new checkpoint that branches from the specified point. The original execution history remains intact.



```python
# Find checkpoint before write_joke
history = list(graph.get_state_history(config))
before_joke = next(s for s in history if s.next == ("write_joke",))

# Fork: update state to change the topic
fork_config = graph.update_state(
    before_joke.config,
    values={"topic": "chickens"},
)

# Resume from the fork — write_joke re-executes with the new topic
fork_result = graph.invoke(None, fork_config)
print(fork_result["joke"])  # A joke about chickens, not socks
```
```

[ ] verified
Reviewer note:

---

## [q016] How can I retrieve stored memories by semantic similarity rather than exact key match?

- **Category:** `single`
- **Source:** https://forum.langchain.com/t/langgraph-cloud-using-the-built-in-postgresql-store-for-long-term-memory-ltm-and-vector-similarity-search/245
- **Must mention:** `store.search`
- **Reference Answer:** Configure the store with an embedding index, then call store.search(namespace, query="...", limit=N) with a natural-language query.

### Evidence Chunks

#### Chunk `cb8c508e1c265c7a` (https://docs.langchain.com/oss/python/langgraph/stores#semantic-search)
**Doc Path:** `stores.mdx` | **Anchor:** `semantic-search`

```text
Beyond simple retrieval, the store also supports semantic search, allowing you to find memories based on meaning rather than exact matches. To enable this, configure the store with an embedding model:

```python
from langchain.embeddings import init_embeddings

store = InMemoryStore(
    index={
        "embed": init_embeddings("openai:text-embedding-3-small"),  # Embedding provider
        "dims": 1536,                              # Embedding dimensions
        "fields": ["food_preference", "$"]              # Fields to embed
    }
)
```


Now when searching, you can use natural language queries to find relevant memories:

```python
# Find memories about food preferences
# (This can be done after putting memories into the store)
memories = store.search(
    namespace_for_memory,
    query="What does the user like to eat?",
    limit=3,  # Return top 3 matches
)
```


You can control which parts of your memories get embedded by configuring the `fields` parameter or by specifying the `index` parameter when storing memories:

```python
# Store with specific fields to embed
store.put(
    namespace_for_memory,
    str(uuid7()),
    {"food_preference": "I love Italian cuisine", "context": "Discussing dinner plans"},
    index=["food_preference"],  # Only embed "food_preferences" field
)

# Store without embedding (still retrievable, but not searchable)
store.put(
    namespace_for_memory, str(uuid7()), {"system_info": "Last updated: 2024-01-01"}, index=False
)
```
```

[ ] verified
Reviewer note:

---

## [q017] What method saves key-value memory data into a hierarchical namespace in BaseStore?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `store.put`
- **Reference Answer:** store.put(namespace, key, value), where namespace is a tuple, key a unique memory id and value a dictionary.

### Evidence Chunks

#### Chunk `2bcb4281380ea615` (https://docs.langchain.com/oss/python/langgraph/stores#basic-usage)
**Doc Path:** `stores.mdx` | **Anchor:** `basic-usage`

```text
The following code snippet shows the @[InMemoryStore] in isolation without using LangGraph:

```python
from langgraph.store.memory import InMemoryStore
store = InMemoryStore()
```

Memories are namespaced by a `tuple`, which is `(, "memories")` in the following example. The namespace can be any length and represent anything, does not have to be user specific.

```python
user_id = "1"
namespace_for_memory = (user_id, "memories")
```

Use the `store.put` method to save memories to the namespace in the store. Specify the namespace, as defined above, and a key-value pair for the memory: the key is simply a unique identifier for the memory (`memory_id`) and the value (a dictionary) is the memory itself.

```python
memory_id = str(uuid7())
memory = {"food_preference": "I like pizza"}
store.put(namespace_for_memory, memory_id, memory)
```

Read out memories from your namespace using the `store.search` method, which returns memories for a given user as a list, up to the `limit` argument (default `10`). With `InMemoryStore`, items are returned in insertion order, so the most recent memory is last in the list; other backends may order memories differently (see Listing items in a namespace).

```python
memories = store.search(namespace_for_memory)
memories[-1].dict()
{
    "value": {"food_preference": "I like pizza"},
    "key": "07e0caf4-1631-47b7-b15f-65515d4c1843",
    "namespace": ["1", "memories"],
    "created_at": "2024-10-02T17:22:31.590602+00:00",
    "updated_at": "2024-10-02T17:22:31.590605+00:00",
}
```

Each memory type is a Python class (`Item`) with certain attributes. We can access it as a dictionary by converting with `.dict`.

The attributes it has are:
```

#### Chunk `85128de843b4ae59` (https://docs.langchain.com/oss/python/langgraph/stores#basic-usage)
**Doc Path:** `stores.mdx` | **Anchor:** `basic-usage`

```text
* `value`: The value (itself a dictionary) of this memory
* `key`: A unique key for this memory in this namespace
* `namespace`: A tuple of strings, the namespace of this memory type

While the type is `tuple[str, ...]`, it may be serialized as a list when converted to JSON (for example, `['1', 'memories']`).

* `created_at`: Timestamp for when this memory was created
* `updated_at`: Timestamp for when this memory was updated
```

[ ] verified
Reviewer note:

---

## [q018] How can I stream model output as individual tokens from my graph?

- **Category:** `single`
- **Source:** https://forum.langchain.com/t/how-to-use-human-in-the-loop-with-stream-mode-messages/1627
- **Must mention:** `messages`
- **Reference Answer:** Pass the messages stream mode to stream or astream to receive 2-tuples of (LLM token, metadata) in real time.

### Evidence Chunks

#### Chunk `b0ad222fb82eb8ef` (https://docs.langchain.com/oss/python/langgraph/streaming#stream-modes)
**Doc Path:** `streaming.mdx` | **Anchor:** `stream-modes`

```text
Pass one or more of the following stream modes as a list to the @[`stream`][CompiledStateGraph.stream] or @[`astream`][CompiledStateGraph.astream] methods:

| Mode | Type | Description |
| :--- | :--- | :---------- |
| values | @[`ValuesStreamPart`] | Full state after each step. |
| updates | @[`UpdatesStreamPart`] | State updates after each step. Multiple updates in the same step are streamed separately. |
| messages | @[`MessagesStreamPart`] | 2-tuples of (LLM token, metadata) from LLM calls. |
| custom | @[`CustomStreamPart`] | Custom data emitted from nodes via @[`get_stream_writer`]. |
| checkpoints | @[`CheckpointStreamPart`] | Checkpoint events (same format as `get_state()`). Requires a checkpointer. |
| tasks | @[`TasksStreamPart`] | Task start/finish events with results and errors. Requires a checkpointer. |
| debug | @[`DebugStreamPart`] | All available info — combines `checkpoints` and `tasks` with extra metadata. |
```

[ ] verified
Reviewer note:

---

## [q019] How do you configure breakpoints to pause execution prior to running specified nodes?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `interrupt_before`
- **Reference Answer:** Set interrupt_before (a list of node names) when compiling the graph, or pass it at invoke time; a checkpointer is required, and resume with invoke(None, config). interrupt_after pauses after a node.

### Evidence Chunks

#### Chunk `31745a815bc93b7b` (https://docs.langchain.com/oss/python/langgraph/interrupts#debugging-with-interrupts)
**Doc Path:** `interrupts.mdx` | **Anchor:** `debugging-with-interrupts`

```text
To debug and test a graph, you can use static interrupts as breakpoints to step through the graph execution one node at a time. Static interrupts are triggered at defined points either before or after a node executes. You can set these by specifying `interrupt_before` and `interrupt_after` when compiling the graph.

Static interrupts are **not** recommended for human-in-the-loop workflows. Use the @[`interrupt`] function instead.

```python
        graph = builder.compile(
            interrupt_before=["node_a"],  # [!code highlight]
            interrupt_after=["node_b", "node_c"],  # [!code highlight]
            checkpointer=checkpointer,
        )

        # Pass a thread ID to the graph
        config = {
            "configurable": {
                "thread_id": "some_thread"
            }
        }

        # Run the graph until the breakpoint
        graph.invoke(inputs, config=config)  # [!code highlight]

        # Resume the graph
        graph.invoke(None, config=config)  # [!code highlight]
        ```

1. The breakpoints are set during `compile` time.
        2. `interrupt_before` specifies the nodes where execution should pause before the node is executed.
        3. `interrupt_after` specifies the nodes where execution should pause after the node is executed.
        4. A checkpointer is required to enable breakpoints.
        5. The graph is run until the first breakpoint is hit.
        6. The graph is resumed by passing in `None` for the input. This will run the graph until the next breakpoint is hit.
```

#### Chunk `7b03ff9dc6a71a13` (https://docs.langchain.com/oss/python/langgraph/interrupts#debugging-with-interrupts)
**Doc Path:** `interrupts.mdx` | **Anchor:** `debugging-with-interrupts`

```text
```python
        config = {
            "configurable": {
                "thread_id": "some_thread"
            }
        }

        # Run the graph until the breakpoint
        graph.invoke(
            inputs,
            interrupt_before=["node_a"],  # [!code highlight]
            interrupt_after=["node_b", "node_c"],  # [!code highlight]
            config=config,
        )

        # Resume the graph
        graph.invoke(None, config=config)  # [!code highlight]
        ```

1. `graph.invoke` is called with the `interrupt_before` and `interrupt_after` parameters. This is a run-time configuration and can be changed for every invocation.
        2. `interrupt_before` specifies the nodes where execution should pause before the node is executed.
        3. `interrupt_after` specifies the nodes where execution should pause after the node is executed.
        4. The graph is run until the first breakpoint is hit.
        5. The graph is resumed by passing in `None` for the input. This will run the graph until the next breakpoint is hit.

To debug your interrupts, use LangSmith.

You can use LangSmith Studio to set static interrupts in your graph in the UI before running the graph. You can also use the UI to inspect the graph state at any point in the execution.
```

[ ] verified
Reviewer note:

---

## [q020] How do I spin up the local development service from the terminal?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `langgraph dev`
- **Reference Answer:** Run langgraph dev to start the LangGraph API server locally (in-memory mode, for development and testing).

### Evidence Chunks

#### Chunk `9886d7a7d1975b69` (https://docs.langchain.com/oss/python/langgraph/local-server#5-launch-agent-server)
**Doc Path:** `local-server.mdx` | **Anchor:** `5-launch-agent-server`

```text
Start the LangGraph API server locally:

```shell
langgraph dev
```


Sample output:

```
INFO:langgraph_api.cli:

        Welcome to

╦  ┌─┐┌┐┌┌─┐╔═╗┬─┐┌─┐┌─┐┬ ┬
║  ├─┤││││ ┬║ ╦├┬┘├─┤├─┘├─┤
╩═╝┴ ┴┘└┘└─┘╚═╝┴└─┴ ┴┴  ┴ ┴

- 🚀 API: http://127.0.0.1:2024
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- 📚 API Docs: http://127.0.0.1:2024/docs

This in-memory server is designed for development and testing.
For production use, please use LangSmith Deployment.
```

The `langgraph dev` command starts Agent Server in an in-memory mode. This mode is suitable for development and testing purposes. For production use, deploy Agent Server with access to a persistent storage backend. For more information, see the Platform setup overview.
```

[ ] verified
Reviewer note:

---

## [q021] Which file configures a LangGraph app for deployment?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `langgraph.json`
- **Reference Answer:** langgraph.json. A LangGraph application consists of graphs, langgraph.json, a dependencies file and an optional .env file.

### Evidence Chunks

#### Chunk `9d8be13faa62417c` (https://docs.langchain.com/oss/python/langgraph/application-structure)
**Doc Path:** `application-structure.mdx` | **Anchor:** ``

```text
A LangGraph application consists of one or more graphs, a configuration file (`langgraph.json`), a file that specifies dependencies, and an optional `.env` file that specifies environment variables.

This guide shows a typical structure of an application and shows you how to provide the required configuration to deploy an application with LangSmith Deployment.


LangSmith Deployment is a managed hosting platform for deploying and scaling LangGraph agents. It handles the infrastructure, scaling, and operational concerns so you can deploy your stateful, long-running agents directly from your repository. Learn more in the Deployment documentation.
```

[ ] verified
Reviewer note:

---

## [q022] Which prebuilt node runs the tools an LLM requested?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `ToolNode`
- **Reference Answer:** ToolNode: a prebuilt node that executes tools, handling parallel tool execution, error handling and state injection.

### Evidence Chunks

#### Chunk `4d77bbc1a5d58dd7` (https://docs.langchain.com/oss/python/langgraph/workflows-agents#toolnode)
**Doc Path:** `workflows-agents.mdx` | **Anchor:** `toolnode`

```text
@[`ToolNode`] is a prebuilt node that executes tools in LangGraph workflows. It handles parallel tool execution, error handling, and state injection automatically.

Use @[`ToolNode`] when you need fine-grained control over how your graph executes tools. This is the building block that powers tool execution in many LangGraph agent patterns.


```python
from langchain.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.graph import MessagesState, StateGraph

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

builder = StateGraph(MessagesState)
builder.add_node("tools", ToolNode([search, calculator]))
# ... add other nodes and edges
graph = builder.compile()
```



#### Access graph state and context from tools

Tools executed by `ToolNode` receive the arguments generated by the model as
their first argument. To read graph-side data that was not generated by the
model, use one of these options:

- In Python, read state and run-scoped context from the injected
  @[`ToolRuntime`] argument.
- In JavaScript, read state and run-scoped context from the tool's second
  argument, typed as @[`ToolRuntime`].


Tools can only access the state values passed to the `ToolNode`. When
`ToolNode` is added directly as a `StateGraph` node, that input is the current
graph state. If you invoke a `ToolNode` manually from another node, pass the
full state when tools need custom state fields. For example, `tool_node.invoke(state)`
or `toolNode.invoke(state, config)` exposes the full state, while passing only
`{"messages": state["messages"]}` or `{ messages: state.messages }` only exposes
`messages`.
```

[ ] verified
Reviewer note:

---

## [q023] How do you ensure state schema changes remain compatible with existing thread checkpoints?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `NotRequired`
- **Reference Answer:** Add new state fields as NotRequired (or Optional with a None default) so old checkpoints still validate.

### Evidence Chunks

#### Chunk `68dc2c547ef50a2c` (https://docs.langchain.com/oss/python/langgraph/backward-compatibility#recommended-patterns)
**Doc Path:** `backward-compatibility.mdx` | **Anchor:** `recommended-patterns`

```text
- Add new state fields as `NotRequired` (or `Optional[...] = None`) so old checkpoints still validate:

  ```python
  from typing import NotRequired
  from typing_extensions import TypedDict

  class State(TypedDict):
      messages: list
      summary: NotRequired[str]  # [!code ++]
  ```

- Treat removals as deprecations. Keep the field defined on the state for at least one drain cycle, even if no node reads it, so existing checkpoints continue to load.
- Rename through *add-then-remove*. Add the new field or node alongside the old one, dual-write or route to both for a deprecation window, then remove the old one once you have confirmed no in-flight thread depends on it.
- Keep node functions tolerant of unknown keys. `TypedDict` ignores extra keys at runtime, so leftover state from an older code version will not raise unless a node explicitly reads a missing key.
- Use time travel and @[`graph.get_state`][get_state] to spot-check existing threads against the new code in a staging deployment before rolling out.
```

[ ] verified
Reviewer note:

---

## [q024] Why does parallel branching fail when two nodes write to the identical state attribute?

- **Category:** `single`
- **Source:** https://github.com/langchain-ai/langgraph/issues/2336
- **Must mention:** `operator.add`
- **Reference Answer:** When several nodes in a fan-out return a value for the same key in one step and the key has no reducer, the graph raises a concurrent update error because it is uncertain how to merge them. Define the key with a reducer, e.g. Annotated[list, operator.add].

### Evidence Chunks

#### Chunk `8938c817a4c2ce9a` (https://docs.langchain.com/oss/python/langgraph/errors/INVALID_CONCURRENT_GRAPH_UPDATE)
**Doc Path:** `errors/INVALID_CONCURRENT_GRAPH_UPDATE.mdx` | **Anchor:** ``

```text
A LangGraph @[`StateGraph`] received concurrent updates to its state from multiple nodes to a state property that doesn't
support it.

One way this can occur is if you are using a fanout
or other parallel execution in your graph and you have defined a graph like this:

```python
from typing import TypedDict

from langgraph.graph import START, StateGraph

class State(TypedDict):
    some_key: str  # [!code highlight]

def node(state: State):
    return {"some_key": "some_string_value"}

def other_node(state: State):
    return {"some_key": "some_string_value"}


builder = StateGraph(State)
builder.add_node(node)
builder.add_node(other_node)
builder.add_edge(START, "node")
builder.add_edge(START, "other_node")
graph = builder.compile()
```


If a node in the above graph returns `{ "some_key": "some_string_value" }`, this will overwrite the state value for `"some_key"` with `"some_string_value"`.
However, if multiple nodes in e.g. a fanout within a single step return values for `"some_key"`, the graph will throw this error because
there is uncertainty around how to update the internal state.


To get around this, you can define a reducer that combines multiple values:

```python
import operator
from typing import Annotated


class State(TypedDict):
    # The operator.add reducer fn makes this append-only  # [!code highlight]
    some_key: Annotated[list, operator.add]  # [!code highlight]
```


This will allow you to define logic that handles the same key returned from multiple nodes executed in parallel.

The following may help resolve this error:

* If your graph executes nodes in parallel, make sure you have defined relevant state keys with a reducer.
```

[ ] verified
Reviewer note:

---

## [q025] What exception is raised when a node function outputs a list rather than a mapping?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `InvalidUpdateError`
- **Reference Answer:** InvalidUpdateError ("Expected dict, got [...]"); nodes must return a dict with keys defined in the state.

### Evidence Chunks

#### Chunk `7df8ede5a20eb979` (https://docs.langchain.com/oss/python/langgraph/errors/INVALID_GRAPH_NODE_RETURN_VALUE)
**Doc Path:** `errors/INVALID_GRAPH_NODE_RETURN_VALUE.mdx` | **Anchor:** ``

```text
A LangGraph @[`StateGraph`]
received a non-dict return type from a node. Here's an example:

```python
from typing import TypedDict

from langgraph.graph import StateGraph

class State(TypedDict):
    some_key: str

def bad_node(state: State):
    # Should return a dict with a value for "some_key", not a list
    return ["whoops"]

builder = StateGraph(State)
builder.add_node(bad_node)
...

graph = builder.compile()
```

Invoking the above graph will result in an error like this:

```python
graph.invoke({"some_key": "someval"})
```

```
InvalidUpdateError: Expected dict, got ['whoops']
For troubleshooting, visit: https://docs.langchain.com/oss/python/langgraph/errors/INVALID_GRAPH_NODE_RETURN_VALUE
```

Nodes in your graph must return a dict containing one or more keys defined in your state.

The following may help resolve this error:

* If you have complex logic in your node, make sure all code paths return an appropriate dict for your defined state.
```

[ ] verified
Reviewer note:

---

## [q026] How can I invoke and test a specific isolated node from a compiled graph?

- **Category:** `single`
- **Source:** https://forum.langchain.com/t/best-practices-for-testing-langgraph-nodes-separately/1396
- **Must mention:** `nodes`
- **Reference Answer:** Access it through compiled_graph.nodes (e.g. compiled_graph.nodes["node1"]) and call invoke() with test input; this bypasses any checkpointer.

### Evidence Chunks

#### Chunk `ab8cf99857cfe02b` (https://docs.langchain.com/oss/python/langgraph/test#testing-individual-nodes-and-edges)
**Doc Path:** `test.mdx` | **Anchor:** `testing-individual-nodes-and-edges`

```text
Compiled LangGraph agents expose references to each individual node as `graph.nodes`. You can take advantage of this to test individual nodes within your agent. Note that this will bypass any checkpointers passed when compiling the graph:

```python
import pytest

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

def create_graph() -> StateGraph:
    class MyState(TypedDict):
        my_key: str

    graph = StateGraph(MyState)
    graph.add_node("node1", lambda state: {"my_key": "hello from node1"})
    graph.add_node("node2", lambda state: {"my_key": "hello from node2"})
    graph.add_edge(START, "node1")
    graph.add_edge("node1", "node2")
    graph.add_edge("node2", END)
    return graph

def test_individual_node_execution() -> None:
    # Will be ignored in this example
    checkpointer = MemorySaver()
    graph = create_graph()
    compiled_graph = graph.compile(checkpointer=checkpointer)
    # Only invoke node 1
    result = compiled_graph.nodes["node1"].invoke(
        {"my_key": "initial_value"},
    )
    assert result["my_key"] == "hello from node1"
```
```

[ ] verified
Reviewer note:

---

## [q027] Which tool lets me visually inspect each step of my agent locally?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `Studio`
- **Reference Answer:** LangSmith Studio, a free visual interface that connects to a locally running agent and shows prompts, tool calls and results, and intermediate states.

### Evidence Chunks

#### Chunk `eb1ae9d4f1d366fb` (https://docs.langchain.com/oss/python/langgraph/studio)
**Doc Path:** `studio.mdx` | **Anchor:** ``

```text
When building agents with LangChain locally, it's helpful to visualize what's happening inside your agent, interact with it in real-time, and debug issues as they occur. **LangSmith Studio** is a free visual interface for developing and testing your LangChain agents from your local machine.

Studio connects to your locally running agent to show you each step your agent takes: the prompts sent to the model, tool calls and their results, and the final output. You can test different inputs, inspect intermediate states, and iterate on your agent's behavior without additional code or deployment.

This pages describes how to set up Studio with your local LangChain agent.
```

[ ] verified
Reviewer note:

---

## [q028] In Pregel, which channel is used by default, and what happens to earlier values?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `LastValue`
- **Reference Answer:** LastValue is the default channel type; it stores the last value written and overwrites any previous value.

### Evidence Chunks

#### Chunk `b6245552f6a0196c` (https://docs.langchain.com/oss/python/langgraph/pregel#topic)
**Doc Path:** `pregel.mdx` | **Anchor:** `topic`

```text
@[`LastValue`] is the default channel type. It stores the last value written to it, overwriting any previous value. Use it for input and output values, or for passing data from one step to the next.

```python
from langgraph.channels import LastValue

channel: LastValue[int] = LastValue(int)
```

@[`Topic`] is a configurable PubSub channel useful for sending multiple values between actors or accumulating output across steps. It can be configured to deduplicate values or to accumulate all values written during a run.

```python
from langgraph.channels import Topic

# Accumulate all values written across steps
channel: Topic[str] = Topic(str, accumulate=True)
```
```

[ ] verified
Reviewer note:

---

## [q029] How do I set up a graph with SQLite persistence and resume an interrupted thread?

- **Category:** `multi`
- **Source:** docs
- **Must mention:** `SqliteSaver`, `Command`
- **Reference Answer:** Install langgraph-checkpoint-sqlite and compile with a SqliteSaver checkpointer, run with a config carrying a thread ID, and resume by calling stream_events(Command(resume=...), version="v3") again.

### Evidence Chunks

#### Chunk `9efb6d35adcf1f17` (https://docs.langchain.com/oss/python/langgraph/checkpointers#checkpointer-libraries)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `checkpointer-libraries`

```text
Under the hood, checkpointing is powered by checkpointer objects that conform to @[`BaseCheckpointSaver`] interface. LangGraph provides several checkpointer implementations, all implemented via standalone, installable libraries.


See checkpointer integrations for available providers.


* `langgraph-checkpoint`: The base interface for checkpointer savers (@[`BaseCheckpointSaver`]) and serialization/deserialization interface (@[`SerializerProtocol`]). Includes in-memory checkpointer implementation (@[`InMemorySaver`]) for experimentation. LangGraph comes with `langgraph-checkpoint` included.
* `langgraph-checkpoint-sqlite`: An implementation of LangGraph checkpointer that uses SQLite database (@[`SqliteSaver`] / @[`AsyncSqliteSaver`]). Ideal for experimentation and local workflows. Needs to be installed separately.
* `langgraph-checkpoint-postgres`: An advanced checkpointer that uses Postgres database (@[`PostgresSaver`] / @[`AsyncPostgresSaver`]), used in LangSmith. Ideal for using in production. Needs to be installed separately.
* `langgraph-checkpoint-mongodb`: An advanced checkpointer that uses MongoDB (`MongoDBSaver` / `AsyncMongoDBSaver`). Ideal for using in production. Needs to be installed separately.
* `langchain-azure-cosmosdb`: An implementation of LangGraph checkpointer that uses Azure Cosmos DB for NoSQL (@[`CosmosDBSaverSync`] / @[`CosmosDBSaver`]). Ideal for using in production with Azure. Supports both sync and async operations, with Microsoft Entra ID authentication. Needs to be installed separately.
```

#### Chunk `f5fb04c45d975bc6` (https://docs.langchain.com/oss/python/langgraph/event-streaming#resume-after-an-interrupt)
**Doc Path:** `event-streaming.mdx` | **Anchor:** `resume-after-an-interrupt`

```text
When a graph pauses for human input, inspect `stream.interrupted` and `stream.interrupts`, then resume by calling `stream_events(..., version="v3")` again with `Command`.

Resume requires a graph compiled with a checkpointer and a config carrying a thread ID — see persistence.

```py
from langgraph.types import Command

stream = graph.stream_events(input, version="v3")

for message in stream.messages:
    print(message.text)

if stream.interrupted:
    print(stream.interrupts)

stream = graph.stream_events(
    Command(resume={"decisions": [{"type": "approve"}]}),
    version="v3",
)
final_state = stream.output
```
```

[ ] verified
Reviewer note:

---

## [q030] How can I retry a failing node automatically and then route to a recovery branch if it still fails?

- **Category:** `multi`
- **Source:** https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574
- **Must mention:** `RetryPolicy`, `Command`
- **Reference Answer:** Add the node with retry_policy=RetryPolicy(...) and error_handler=handler; once retries are exhausted the handler runs and can return Command(update=..., goto=...) to route to a compensation node. error_handler requires langgraph>=1.2.
- **Notes:** Replaced the default-behavior evidence chunk, which does not support the answer, with error-handling.

### Evidence Chunks

#### Chunk `21cf6cebc6be0c62` (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#error-handling)
**Doc Path:** `fault-tolerance.mdx` | **Anchor:** `error-handling`

```text
Requires `langgraph>=1.2`.



An error handler runs after a node fails and all retries are exhausted. It receives the current state and can update it or route to a different node using @[`Command`]. This is useful for compensation flows (Saga patterns) where you want to recover gracefully rather than abort the entire graph.

Pass `error_handler=` to @[`add_node`]:

```python
from langgraph.errors import NodeError
from langgraph.types import Command, RetryPolicy
from langgraph.graph import StateGraph, START
from typing_extensions import TypedDict

class State(TypedDict):
    status: str

def charge_payment(state: State) -> State:
    raise RuntimeError("payment gateway timeout")

def payment_error_handler(state: State, error: NodeError) -> Command:
    return Command(
        update={"status": f"compensated: {error.error}"},
        goto="finalize",
    )

def finalize(state: State) -> State:
    return state

graph = (
    StateGraph(State)
    .add_node(
        "charge_payment",
        charge_payment,
        retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
        error_handler=payment_error_handler,
    )
    .add_node("finalize", finalize)
    .add_edge(START, "charge_payment")
    .compile()
)
```


The handler fires only after the retry policy is exhausted, or immediately if no retry policy is configured. The retry policy and the error handler stay decoupled: configure when to retry and when to compensate independently.
```

#### Chunk `05aae600ce109ffa` (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#route-with-command)
**Doc Path:** `fault-tolerance.mdx` | **Anchor:** `route-with-command`

```text
Error handlers can return a @[`Command`] to update state and route to a specific node, enabling Saga / compensation patterns:

```python
from langgraph.errors import NodeError
from langgraph.types import Command, RetryPolicy
from langgraph.graph import StateGraph, START
from typing_extensions import TypedDict

class State(TypedDict):
    status: str

def reserve_inventory(state: State) -> State:
    return {"status": "reserved"}

def charge_payment(state: State) -> State:
    raise RuntimeError("payment timeout")

def payment_error_handler(state: State, error: NodeError) -> Command:
    return Command(
        update={"status": f"compensated_after_{error.node}: {error.error}"},
        goto="finalize",
    )

def finalize(state: State) -> State:
    return state

graph = (
    StateGraph(State)
    .add_node("reserve_inventory", reserve_inventory)
    .add_node(
        "charge_payment",
        charge_payment,
        retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
        error_handler=payment_error_handler,
    )
    .add_node("finalize", finalize)
    .add_edge(START, "reserve_inventory")
    .add_edge("reserve_inventory", "charge_payment")
    .compile()
)
```

`charge_payment` retries on `ConnectionError` up to 3 times. If retries are exhausted (or the error isn't a `ConnectionError`), the handler compensates by updating state and routing to `finalize` instead of aborting the graph.
```

[ ] verified
Reviewer note:

---

## [q031] Can I embed one compiled graph inside another graph, and where does the checkpointer go?

- **Category:** `multi`
- **Source:** https://stackoverflow.com/questions/78541330/can-i-merge-or-compose-graphs-in-langgraph
- **Must mention:** `checkpointer`
- **Reference Answer:** A compiled subgraph can be added as a node of the parent when it shares state keys. When schemas differ, call the subgraph's invoke inside a node function that maps parent state to subgraph state and back. Provide the checkpointer only when compiling the parent and it propagates to child subgraphs.
- **Notes:** Rewritten: the old reference attached compiled subgraphs directly as nodes, which only one of the two evidence sections supports. The use-subgraphs anchor holds several large example chunks; consider chunk-level gold ids.

### Evidence Chunks

#### Chunk `235b0bdf5e99602a` (https://docs.langchain.com/oss/python/langgraph/add-memory#use-in-subgraphs)
**Doc Path:** `add-memory.mdx` | **Anchor:** `use-in-subgraphs`

```text
If your graph contains subgraphs, you only need to provide the checkpointer when compiling the parent graph. LangGraph will automatically propagate the checkpointer to the child subgraphs.

```python
from langgraph.graph import START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from typing import TypedDict

class State(TypedDict):
    foo: str

# Subgraph

def subgraph_node_1(state: State):
    return {"foo": state["foo"] + "bar"}

subgraph_builder = StateGraph(State)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph = subgraph_builder.compile()  # [!code highlight]

# Parent graph

builder = StateGraph(State)
builder.add_node("node_1", subgraph)  # [!code highlight]
builder.add_edge(START, "node_1")

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)  # [!code highlight]
```


You can configure subgraph-specific checkpointing behavior. See subgraph persistence for details on persistence levels including interrupt support and stateful continuations.

```python
subgraph_builder = StateGraph(...)
subgraph = subgraph_builder.compile(checkpointer=True)  # [!code highlight]
```
```

#### Chunk `f7ae465ad3a0486c` (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#call-a-subgraph-inside-a-node)
**Doc Path:** `use-subgraphs.mdx` | **Anchor:** `call-a-subgraph-inside-a-node`

```text
When the parent graph and subgraph have **different state schemas** (no shared keys), invoke the subgraph inside a node function. This is common when you want to keep a private message history for each agent in a multi-agent system.

The node function transforms the parent state to the subgraph state before invoking the subgraph, and transforms the results back to the parent state before returning.

```python
from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START

class SubgraphState(TypedDict):
    bar: str

# Subgraph

def subgraph_node_1(state: SubgraphState):
    return {"bar": "hi! " + state["bar"]}

subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph = subgraph_builder.compile()

# Parent graph

class State(TypedDict):
    foo: str

def call_subgraph(state: State):
    # Transform the state to the subgraph state
    subgraph_output = subgraph.invoke({"bar": state["foo"]})  # [!code highlight]
    # Transform response back to the parent state
    return {"foo": subgraph_output["bar"]}

builder = StateGraph(State)
builder.add_node("node_1", call_subgraph)
builder.add_edge(START, "node_1")
graph = builder.compile()
```
```

#### Chunk `b59fec0a6548c02b` (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#call-a-subgraph-inside-a-node)
**Doc Path:** `use-subgraphs.mdx` | **Anchor:** `call-a-subgraph-inside-a-node`

```text
```python
  from typing_extensions import TypedDict
  from langgraph.graph.state import StateGraph, START
  from langgraph.stream import UpdatesTransformer

  # Define subgraph
  class SubgraphState(TypedDict):
      # note that none of these keys are shared with the parent graph state
      bar: str
      baz: str

  def subgraph_node_1(state: SubgraphState):
      return {"baz": "baz"}

  def subgraph_node_2(state: SubgraphState):
      return {"bar": state["bar"] + state["baz"]}

  subgraph_builder = StateGraph(SubgraphState)
  subgraph_builder.add_node(subgraph_node_1)
  subgraph_builder.add_node(subgraph_node_2)
  subgraph_builder.add_edge(START, "subgraph_node_1")
  subgraph_builder.add_edge("subgraph_node_1", "subgraph_node_2")
  subgraph = subgraph_builder.compile()

  # Define parent graph
  class ParentState(TypedDict):
      foo: str

  def node_1(state: ParentState):
      return {"foo": "hi! " + state["foo"]}

  def node_2(state: ParentState):
      # Transform the state to the subgraph state
      response = subgraph.invoke({"bar": state["foo"]})
      # Transform response back to the parent state
      return {"foo": response["bar"]}


  builder = StateGraph(ParentState)
  builder.add_node("node_1", node_1)
  builder.add_node("node_2", node_2)
  builder.add_edge(START, "node_1")
  builder.add_edge("node_1", "node_2")
  graph = builder.compile()

  stream = graph.stream_events({"foo": "foo"}, version="v3", transformers=[UpdatesTransformer])
  for event in stream:
      if event["method"] == "updates":
          print(event["params"]["namespace"], event["params"]["data"])
  ```
```

#### Chunk `95e5678a6aff2964` (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#call-a-subgraph-inside-a-node)
**Doc Path:** `use-subgraphs.mdx` | **Anchor:** `call-a-subgraph-inside-a-node`

```text
```
  [] {'node_1': {'foo': 'hi! foo'}}
  ['node_2:577b710b-64ae-31fb-9455-6a4d4cc2b0b9'] {'subgraph_node_1': {'baz': 'baz'}}
  ['node_2:577b710b-64ae-31fb-9455-6a4d4cc2b0b9'] {'subgraph_node_2': {'bar': 'hi! foobaz'}}
  [] {'node_2': {'foo': 'hi! foobaz'}}
  ```

This is an example with two levels of subgraphs: parent -> child -> grandchild.
```

#### Chunk `a45b96a7faff4e9a` (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#call-a-subgraph-inside-a-node)
**Doc Path:** `use-subgraphs.mdx` | **Anchor:** `call-a-subgraph-inside-a-node`

```text
```python
  # Grandchild graph
  from typing_extensions import TypedDict
  from langgraph.graph.state import StateGraph, START, END
  from langgraph.stream import UpdatesTransformer

  class GrandChildState(TypedDict):
      my_grandchild_key: str

  def grandchild_1(state: GrandChildState) -> GrandChildState:
      # NOTE: child or parent keys will not be accessible here
      return {"my_grandchild_key": state["my_grandchild_key"] + ", how are you"}


  grandchild = StateGraph(GrandChildState)
  grandchild.add_node("grandchild_1", grandchild_1)

  grandchild.add_edge(START, "grandchild_1")
  grandchild.add_edge("grandchild_1", END)

  grandchild_graph = grandchild.compile()

  # Child graph
  class ChildState(TypedDict):
      my_child_key: str

  def call_grandchild_graph(state: ChildState) -> ChildState:
      # NOTE: parent or grandchild keys won't be accessible here
      grandchild_graph_input = {"my_grandchild_key": state["my_child_key"]}
      grandchild_graph_output = grandchild_graph.invoke(grandchild_graph_input)
      return {"my_child_key": grandchild_graph_output["my_grandchild_key"] + " today?"}

  child = StateGraph(ChildState)
  # We're passing a function here instead of just compiled graph (`grandchild_graph`)
  child.add_node("child_1", call_grandchild_graph)
  child.add_edge(START, "child_1")
  child.add_edge("child_1", END)
  child_graph = child.compile()

  # Parent graph
  class ParentState(TypedDict):
      my_key: str

  def parent_1(state: ParentState) -> ParentState:
      # NOTE: child or grandchild keys won't be accessible here
      return {"my_key": "hi " + state["my_key"]}

  def parent_2(state: ParentState) -> ParentState:
      return {"my_key": state["my_key"] + " bye!"}

  def call_child_graph(state: ParentState) -> ParentState:
      child_graph_input = {"my_child_key": state["my_key"]}
      child_graph_output = child_graph.invoke(child_graph_input)
      return {"my_key": child_graph_output["my_child_key"]}

  parent = StateGraph(ParentState)
  parent.add_node("parent_1", parent_1)
  # We're passing a function here instead of just a compiled graph (`child_graph`)
  parent.add_node("child", call_child_graph)
  parent.add_node("parent_2", parent_2)

  parent.add_edge(START, "parent_1")
  parent.add_edge("parent_1", "child")
  parent.add_edge("child", "parent_2")
  parent.add_edge("parent_2", END)

  parent_graph = parent.compile()

  stream = parent_graph.stream_events({"my_key": "Bob"}, version="v3", transformers=[UpdatesTransformer])
  for event in stream:
      if event["method"] == "updates":
          print(event["params"]["namespace"], event["params"]["data"])
  ```
```

#### Chunk `014138ce682349c8` (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#call-a-subgraph-inside-a-node)
**Doc Path:** `use-subgraphs.mdx` | **Anchor:** `call-a-subgraph-inside-a-node`

```text
```
  [] {'parent_1': {'my_key': 'hi Bob'}}
  ['child:2e26e9ce-602f-862c-aa66-1ea5a4655e3b', 'child_1:781bb3b1-3971-84ce-810b-acf819a03f9c'] {'grandchild_1': {'my_grandchild_key': 'hi Bob, how are you'}}
  ['child:2e26e9ce-602f-862c-aa66-1ea5a4655e3b'] {'child_1': {'my_child_key': 'hi Bob, how are you today?'}}
  [] {'child': {'my_key': 'hi Bob, how are you today?'}}
  [] {'parent_2': {'my_key': 'hi Bob, how are you today? bye!'}}
  ```
```

[ ] verified
Reviewer note:

---

## [q032] How can I configure both short-term conversational memory and long-term user profile stores?

- **Category:** `multi`
- **Source:** https://forum.langchain.com/t/can-create-supervisor-create-react-agent-use-checkpointer-and-store-for-across-thread-memory/1779
- **Must mention:** `checkpointer`, `store`
- **Reference Answer:** Compile the graph with both a checkpointer (thread-scoped short-term memory) and a store (cross-thread long-term memory), e.g. builder.compile(checkpointer=checkpointer, store=store); nodes reach the store via the Runtime object.

### Evidence Chunks

#### Chunk `8891e840c03d5443` (https://docs.langchain.com/oss/python/langgraph/add-memory#add-long-term-memory)
**Doc Path:** `add-memory.mdx` | **Anchor:** `add-long-term-memory`

```text
Use long-term memory to store user-specific or application-specific data across conversations.

```python
from langgraph.store.memory import InMemoryStore  # [!code highlight]
from langgraph.graph import StateGraph

store = InMemoryStore()  # [!code highlight]

builder = StateGraph(...)
graph = builder.compile(store=store)  # [!code highlight]
```
```

#### Chunk `bcadf7322547cf2e` (https://docs.langchain.com/oss/python/langgraph/stores#using-in-langgraph)
**Doc Path:** `stores.mdx` | **Anchor:** `using-in-langgraph`

```text
The store works hand-in-hand with the checkpointer: the checkpointer saves state to threads, as discussed above, and the store allows you to store arbitrary information for access _across_ threads. Compile the graph with both the checkpointer and the store as follows.

```python
from dataclasses import dataclass
from langgraph.checkpoint.memory import InMemorySaver

@dataclass
class Context:
    user_id: str

# We need this because we want to enable threads (conversations)
checkpointer = InMemorySaver()

# ... Define the graph ...

# Compile the graph with the checkpointer and store
builder = StateGraph(MessagesState, context_schema=Context)
# ... add nodes and edges ...
graph = builder.compile(checkpointer=checkpointer, store=store)
```

Then invoke the graph with a `thread_id`, as before, and also with a `user_id`, which serves as the namespace for memories for this particular user as before.

```python
# Invoke the graph
config = {"configurable": {"thread_id": "1"}}

# First let's just say hi to the AI
for update in graph.stream(
    {"messages": [{"role": "user", "content": "hi"}]},
    config,
    stream_mode="updates",
    context=Context(user_id="1"),
):
    print(update)
```

You can access the store and the `user_id` from _any node_ by using the `Runtime` object. The `Runtime` is automatically injected by LangGraph when you add it as a parameter to your node function. You can use it to save memories:
```

#### Chunk `f3e704dfdd7e2cda` (https://docs.langchain.com/oss/python/langgraph/stores#using-in-langgraph)
**Doc Path:** `stores.mdx` | **Anchor:** `using-in-langgraph`

```text
```python
from langgraph.runtime import Runtime
from dataclasses import dataclass

@dataclass
class Context:
    user_id: str

async def update_memory(state: MessagesState, runtime: Runtime[Context]):

    # Get the user id from the runtime context
    user_id = runtime.context.user_id

    # Namespace the memory
    namespace = (user_id, "memories")

    # ... Analyze conversation and create a new memory

    # Create a new memory ID
    memory_id = str(uuid7())

    # We create a new memory
    await runtime.store.aput(namespace, memory_id, {"memory": memory})

```

You can also access the store from any node and use the `store.search` method to get memories. Memories are returned as a list of objects that can be converted to a dictionary.

```python
memories[-1].dict()
{
    "value": {"food_preference": "I like pizza"},
    "key": "07e0caf4-1631-47b7-b15f-65515d4c1843",
    "namespace": ["1", "memories"],
    "created_at": "2024-10-02T17:22:31.590602+00:00",
    "updated_at": "2024-10-02T17:22:31.590605+00:00",
}
```

You access the memories and use them in model calls.

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime


@dataclass
class Context:
    user_id: str


async def call_model(state: MessagesState, runtime: Runtime[Context]):
    # Get the user id from the runtime context
    user_id = runtime.context.user_id

    # Namespace the memory
    namespace = (user_id, "memories")

    # Search based on the most recent message
    memories = await runtime.store.asearch(namespace, query=state["messages"][-1].content, limit=3)
    info = "\n".join([d.value["memory"] for d in memories])

    # ... Use memories in the model call
```
```

#### Chunk `47a03fde39c98196` (https://docs.langchain.com/oss/python/langgraph/stores#using-in-langgraph)
**Doc Path:** `stores.mdx` | **Anchor:** `using-in-langgraph`

```text
If you create a new thread, you can still access the same memories so long as the `user_id` is the same.

```python
# Invoke the graph on a new thread
config = {"configurable": {"thread_id": "2"}}

# Let's say hi again
for update in graph.stream(
    {"messages": [{"role": "user", "content": "hi, tell me about my memories"}]},
    config,
    stream_mode="updates",
    context=Context(user_id="1"),
):
    print(update)
```

When you use LangSmith locally (e.g., in Studio) or hosted, the base store is available to use by default and you do not need to specify it during graph compilation. To enable semantic search, however, you **do** need to configure the indexing settings in your `langgraph.json` file. For example:

```json
{
    ...
    "store": {
        "index": {
            "embed": "openai:text-embeddings-3-small",
            "dims": 1536,
            "fields": ["$"]
        }
    }
}
```

See the deployment guide for more details and configuration options.

To use a storage backend other than the built-in implementations, subclass @[BaseStore] and implement its required methods. The built-in @[InMemoryStore] is the simplest reference implementation.
```

[ ] verified
Reviewer note:

---

## [q033] When an orchestrator dispatches sub-agents through tools, how do I print the parent agent's own tokens and also follow each sub-agent's messages from a single streaming run?

- **Category:** `multi`
- **Source:** https://forum.langchain.com/t/streaming-from-sub-agents-in-the-subagents-pattern/2768
- **Must mention:** `stream_events`, `subgraphs`
- **Reference Answer:** Call graph.stream_events(input, version="v3"). Iterate stream.messages and print the tokens of each message.text to stream the parent's output, and iterate stream.subgraphs to follow nested work: each subgraph exposes graph_name, path and its own messages, and a named agent dispatched from a tool appears under its name.
- **Notes:** Old reference said stream_events takes subgraphs=True. The evidence shows stream.subgraphs on the returned stream; subgraphs=True belongs to stream/get_state.

### Evidence Chunks

#### Chunk `cc15c7cc538f0119` (https://docs.langchain.com/oss/python/langgraph/event-streaming#quickstart)
**Doc Path:** `event-streaming.mdx` | **Anchor:** `quickstart`

```text
Event streaming is the recommended in-process streaming model for most LangGraph application code. It returns a run stream object that can be consumed in multiple ways at the same time.

```py
stream = graph.stream_events({
    "messages": [{"role": "user", "content": "What is 42 * 17?"}],
}, version="v3")

for message in stream.messages:
    for token in message.text:
        print(token, end="", flush=True)

final_state = stream.output
```


To stream against a graph deployed behind an Agent Server, see the LangSmith Streaming API.
```

#### Chunk `2c6d8f38713f8d5d` (https://docs.langchain.com/oss/python/langgraph/event-streaming#stream-subgraphs)
**Doc Path:** `event-streaming.mdx` | **Anchor:** `stream-subgraphs`

```text
Use `stream.subgraphs` to observe nested graph work without parsing namespace strings:

```py
stream = graph.stream_events(input, version="v3")

for subgraph in stream.subgraphs:
    print(subgraph.graph_name, subgraph.path)

    for message in subgraph.messages:
        print(message.text)
```


`subgraph.graph_name` is the `name` of the compiled graph or agent. A named agent dispatched from a tool (for example, a `create_agent(name=...)` invoked through the Deep Agents `task` tool) surfaces here under that name, and the `lifecycle` event that opens the scope carries a `cause` linking back to the dispatching tool call. See Lifecycle for more information.

For product-specific streams, see Deep Agents streaming for subagent streams and LangChain agent streaming for tool calls and middleware events.
```

[ ] verified
Reviewer note:

---

## [q034] How do I read the saved state of a thread and then edit it?

- **Category:** `multi`
- **Source:** docs
- **Must mention:** `get_state`, `update_state`
- **Reference Answer:** Fetch the latest StateSnapshot with graph.get_state(config) (values, next, tasks), then edit it with update_state(config, values), which creates a new checkpoint passed through reducers.
- **Notes:** Removed the 'continue with Command' step: no evidence chunk supports it.

### Evidence Chunks

#### Chunk `2661915e250cbc54` (https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `get-state`

```text
When interacting with the saved graph state, you **must** specify a thread identifier. You can view the _latest_ state of the graph by calling `graph.get_state(config)`. This will return a `StateSnapshot` object that corresponds to the latest checkpoint associated with the thread ID provided in the config or a checkpoint associated with a checkpoint ID for the thread, if provided.

```python
# get the latest state snapshot
config = {"configurable": {"thread_id": "1"}}
graph.get_state(config)

# get a state snapshot for a specific checkpoint_id
config = {"configurable": {"thread_id": "1", "checkpoint_id": "1ef663ba-28fe-6528-8002-5a559208592c"}}
graph.get_state(config)
```

In this example, the output of `get_state` will look like this:

```
StateSnapshot(
    values={'foo': 'b', 'bar': ['a', 'b']},
    next=(),
    config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28fe-6528-8002-5a559208592c'}},
    metadata={'source': 'loop', 'writes': {'node_b': {'foo': 'b', 'bar': ['b']}}, 'step': 2},
    created_at='2024-08-29T19:19:38.821749+00:00',
    parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1ef663ba-28f9-6ec4-8001-31981c2c39f8'}},
    tasks=()
)
```

#### StateSnapshot fields
```

#### Chunk `dfa40deca1c1011a` (https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `get-state`

```text
| Field | Type | Description |
|-------|------|-------------|
| `values` | `dict` | State channel values at this checkpoint. |
| `next` | `tuple[str, ...]` | Node names to execute next. Empty `()` means the graph is complete. |
| `config` | `dict` | Contains `thread_id`, `checkpoint_ns`, and `checkpoint_id`. |
| `metadata` | `dict` | Execution metadata. Contains `source` (`"input"`, `"loop"`, or `"update"`), `writes` (node outputs), and `step` (super-step counter). |
| `created_at` | `str` | ISO 8601 timestamp of when this checkpoint was created. |
| `parent_config` | `dict \| None` | Config of the previous checkpoint. `None` for the first checkpoint. |
| `tasks` | `tuple[PregelTask, ...]` | Tasks to execute at this step. Each task has `id`, `name`, `error`, `interrupts`, and optionally `state` (subgraph snapshot, when using `subgraphs=True`). |
```

#### Chunk `39bfcdd6dee87c7d` (https://docs.langchain.com/oss/python/langgraph/checkpointers#update-state)
**Doc Path:** `checkpointers.mdx` | **Anchor:** `update-state`

```text
You can edit the graph state using @`update_state`]. This creates a new checkpoint with the updated values — it does not modify the original checkpoint. The update is treated the same as a node update: values are passed through [reducer functions when defined, so channels with reducers _accumulate_ values rather than overwrite them.

You can optionally specify `as_node` to control which node the update is treated as coming from, which affects which node executes next. See Time travel: `as_node` for details.
```

[ ] verified
Reviewer note:

---

## [q035] What is required to migrate from a functional workflow into a full StateGraph definition?

- **Category:** `multi`
- **Source:** docs
- **Must mention:** `entrypoint`, `StateGraph`
- **Reference Answer:** Define a TypedDict state schema and replace the @entrypoint function with a StateGraph: each task becomes a node (add_node) and Python branching becomes add_conditional_edges with routing functions.

### Evidence Chunks

#### Chunk `4e87bf3df084938d` (https://docs.langchain.com/oss/python/langgraph/functional-api#example)
**Doc Path:** `functional-api.mdx` | **Anchor:** `example`

```text
Below we demonstrate a simple application that writes an essay and interrupts to request human review.

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import interrupt

@task
def write_essay(topic: str) -> str:
    """Write an essay about the given topic."""
    time.sleep(1) # A placeholder for a long-running task.
    return f"An essay about topic: {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> dict:
    """A simple workflow that writes an essay and asks for a review."""
    essay = write_essay("cat").result()
    is_approved = interrupt({
        # Any json-serializable payload provided to interrupt as argument.
        # It will be surfaced on the client side as an Interrupt when streaming data
        # from the workflow.
        "essay": essay, # The essay we want reviewed.
        # We can add any additional information that we need.
        # For example, introduce a key called "action" with some instructions.
        "action": "Please approve/reject the essay",
    })

    return {
        "essay": essay, # The essay that was generated
        "is_approved": is_approved, # Response from HIL
    }
```

This workflow will write an essay about the topic "cat" and then pause to get a review from a human. The workflow can be interrupted for an indefinite amount of time until a review is provided.

When the workflow is resumed, it executes from the very start, but because the result of the `writeEssay` task was already saved, the task result will be loaded from the checkpoint instead of being recomputed.

An essay has been written and is ready for review. Once the review is provided, we can resume the workflow:
```

#### Chunk `a0fccbb865ec2164` (https://docs.langchain.com/oss/python/langgraph/functional-api#example)
**Doc Path:** `functional-api.mdx` | **Anchor:** `example`

```text
The workflow has been completed and the review has been added to the essay.

The @`@entrypoint`] decorator can be used to create a workflow from a function. It encapsulates workflow logic and manages execution flow, including handling _long-running tasks_ and [interrupts.
```

#### Chunk `7ce044015429a1c0` (https://docs.langchain.com/oss/python/langgraph/choosing-apis#from-functional-to-graph-api)
**Doc Path:** `choosing-apis.mdx` | **Anchor:** `from-functional-to-graph-api`

```text
When your functional workflow grows complex, you can migrate to the Graph API:


```python
# Before: Functional API
@entrypoint(checkpointer=checkpointer)
def complex_workflow(input_data: dict) -> dict:
    step1 = process_step1(input_data).result()

    if step1["needs_analysis"]:
        analysis = analyze_data(step1).result()
        if analysis["confidence"] > 0.8:
            result = high_confidence_path(analysis).result()
        else:
            result = low_confidence_path(analysis).result()
    else:
        result = simple_path(step1).result()

    return result

# After: Graph API
class WorkflowState(TypedDict):
    input_data: dict
    step1_result: dict
    analysis: dict
    final_result: dict

def should_analyze(state):
    return "analyze" if state["step1_result"]["needs_analysis"] else "simple_path"

def confidence_check(state):
    return "high_confidence" if state["analysis"]["confidence"] > 0.8 else "low_confidence"

workflow = StateGraph(WorkflowState)
workflow.add_node("step1", process_step1_node)
workflow.add_conditional_edges("step1", should_analyze)
workflow.add_node("analyze", analyze_data_node)
workflow.add_conditional_edges("analyze", confidence_check)
# ... add remaining nodes and edges
```
```

[ ] verified
Reviewer note:

---

## [q036] How can I build an agent that queries a database and stores summaries across conversations?

- **Category:** `multi`
- **Source:** docs
- **Must mention:** `sql_db_query`, `store`
- **Reference Answer:** Give the agent database tools (e.g. sql_db_list_tables, sql_db_schema, sql_db_query) and compile the graph with a store so summaries are saved under a namespace and readable across threads.

### Evidence Chunks

#### Chunk `13c4a6dc9b720c7f` (https://docs.langchain.com/oss/python/langgraph/sql-agent#3-add-tools-for-database-interactions)
**Doc Path:** `sql-agent.mdx` | **Anchor:** `3-add-tools-for-database-interactions`

```text
The following database tools are minimal wrappers for demonstration purposes only. They are not intended to be secure or used in production. Use narrowly scoped database permissions and add application-specific validation before executing model-generated SQL.


We can implement database tools as thin wrappers using the `@tool` decorator from `langchain.tools`:


```
sql_db_list_tables: Input is an empty string, output is a comma-separated list of tables in the database.

sql_db_schema: Input to this tool is a comma-separated list of tables, output is the schema and sample rows for those tables.
    Be sure that the tables actually exist by calling sql_db_list_tables first!
    Example Input: table1, table2, table3

sql_db_query: Input to this tool is a detailed and correct SQL query, output is a result from the database.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    If you encounter an issue with Unknown column 'xxxx' in 'field list', use sql_db_schema to query the correct table fields.
```
```

#### Chunk `bcadf7322547cf2e` (https://docs.langchain.com/oss/python/langgraph/stores#using-in-langgraph)
**Doc Path:** `stores.mdx` | **Anchor:** `using-in-langgraph`

```text
The store works hand-in-hand with the checkpointer: the checkpointer saves state to threads, as discussed above, and the store allows you to store arbitrary information for access _across_ threads. Compile the graph with both the checkpointer and the store as follows.

```python
from dataclasses import dataclass
from langgraph.checkpoint.memory import InMemorySaver

@dataclass
class Context:
    user_id: str

# We need this because we want to enable threads (conversations)
checkpointer = InMemorySaver()

# ... Define the graph ...

# Compile the graph with the checkpointer and store
builder = StateGraph(MessagesState, context_schema=Context)
# ... add nodes and edges ...
graph = builder.compile(checkpointer=checkpointer, store=store)
```

Then invoke the graph with a `thread_id`, as before, and also with a `user_id`, which serves as the namespace for memories for this particular user as before.

```python
# Invoke the graph
config = {"configurable": {"thread_id": "1"}}

# First let's just say hi to the AI
for update in graph.stream(
    {"messages": [{"role": "user", "content": "hi"}]},
    config,
    stream_mode="updates",
    context=Context(user_id="1"),
):
    print(update)
```

You can access the store and the `user_id` from _any node_ by using the `Runtime` object. The `Runtime` is automatically injected by LangGraph when you add it as a parameter to your node function. You can use it to save memories:
```

#### Chunk `f3e704dfdd7e2cda` (https://docs.langchain.com/oss/python/langgraph/stores#using-in-langgraph)
**Doc Path:** `stores.mdx` | **Anchor:** `using-in-langgraph`

```text
```python
from langgraph.runtime import Runtime
from dataclasses import dataclass

@dataclass
class Context:
    user_id: str

async def update_memory(state: MessagesState, runtime: Runtime[Context]):

    # Get the user id from the runtime context
    user_id = runtime.context.user_id

    # Namespace the memory
    namespace = (user_id, "memories")

    # ... Analyze conversation and create a new memory

    # Create a new memory ID
    memory_id = str(uuid7())

    # We create a new memory
    await runtime.store.aput(namespace, memory_id, {"memory": memory})

```

You can also access the store from any node and use the `store.search` method to get memories. Memories are returned as a list of objects that can be converted to a dictionary.

```python
memories[-1].dict()
{
    "value": {"food_preference": "I like pizza"},
    "key": "07e0caf4-1631-47b7-b15f-65515d4c1843",
    "namespace": ["1", "memories"],
    "created_at": "2024-10-02T17:22:31.590602+00:00",
    "updated_at": "2024-10-02T17:22:31.590605+00:00",
}
```

You access the memories and use them in model calls.

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime


@dataclass
class Context:
    user_id: str


async def call_model(state: MessagesState, runtime: Runtime[Context]):
    # Get the user id from the runtime context
    user_id = runtime.context.user_id

    # Namespace the memory
    namespace = (user_id, "memories")

    # Search based on the most recent message
    memories = await runtime.store.asearch(namespace, query=state["messages"][-1].content, limit=3)
    info = "\n".join([d.value["memory"] for d in memories])

    # ... Use memories in the model call
```
```

#### Chunk `47a03fde39c98196` (https://docs.langchain.com/oss/python/langgraph/stores#using-in-langgraph)
**Doc Path:** `stores.mdx` | **Anchor:** `using-in-langgraph`

```text
If you create a new thread, you can still access the same memories so long as the `user_id` is the same.

```python
# Invoke the graph on a new thread
config = {"configurable": {"thread_id": "2"}}

# Let's say hi again
for update in graph.stream(
    {"messages": [{"role": "user", "content": "hi, tell me about my memories"}]},
    config,
    stream_mode="updates",
    context=Context(user_id="1"),
):
    print(update)
```

When you use LangSmith locally (e.g., in Studio) or hosted, the base store is available to use by default and you do not need to specify it during graph compilation. To enable semantic search, however, you **do** need to configure the indexing settings in your `langgraph.json` file. For example:

```json
{
    ...
    "store": {
        "index": {
            "embed": "openai:text-embeddings-3-small",
            "dims": 1536,
            "fields": ["$"]
        }
    }
}
```

See the deployment guide for more details and configuration options.

To use a storage backend other than the built-in implementations, subclass @[BaseStore] and implement its required methods. The built-in @[InMemoryStore] is the simplest reference implementation.
```

[ ] verified
Reviewer note:

---

## [q037] How do I pause graph execution inside a node to wait for human approval?

- **Category:** `version`
- **Source:** docs
- **Must mention:** `interrupt`
- **Reference Answer:** Call the interrupt function directly within the node to suspend execution and wait for human input; a checkpointer and thread ID are required.
- **Notes:** Before langgraph 0.2.47 there was no interrupt() function. It was added in 0.2.47 (older code relied on NodeInterrupt or static breakpoints). Proof: https://github.com/langchain-ai/langgraph/releases/tag/0.2.47

### Evidence Chunks

#### Chunk `43d2773fee2c265d` (https://docs.langchain.com/oss/python/langgraph/interrupts#pause-using-interrupt)
**Doc Path:** `interrupts.mdx` | **Anchor:** `pause-using-interrupt`

```text
The @[`interrupt`] function pauses graph execution and returns a value to the caller. When you call @[`interrupt`] within a node, LangGraph saves the current graph state and waits for you to resume execution with input.

To use @[`interrupt`], you need:
1. A **checkpointer** to persist the graph state (use a durable checkpointer in production)
2. A **thread ID** in your config so the runtime knows which state to resume from
3. To call `interrupt()` where you want to pause (payload must be JSON-serializable)

```python
from langgraph.types import interrupt

def approval_node(state: State):
    # Pause and ask for approval
    approved = interrupt("Do you approve this action?")

    # When you resume, Command(resume=...) returns that value here
    return {"approved": approved}
```


When you call @[`interrupt`], here's what happens:

1. **Graph execution gets suspended** at the exact point where @[`interrupt`] is called
2. **State is saved** using the checkpointer so execution can be resumed later, In production, this should be a persistent checkpointer (e.g. backed by a database)
3. **Value is returned** to the caller on `stream.interrupts` when using event streaming (`graph.stream_events(..., version="v3")`), or under `__interrupt__` with the default `invoke()` API; it can be any JSON-serializable value (string, object, array, etc.)
4. **Graph waits indefinitely** until you resume execution with a response
5. **Response is passed back** into the node when you resume, becoming the return value of the `interrupt()` call
```

[ ] verified
Reviewer note:

---

## [q038] How should a paused graph execution be resumed with user provided data?

- **Category:** `version`
- **Source:** docs
- **Must mention:** `Command`, `resume`
- **Reference Answer:** Resume by calling invoke or stream_events again with Command(resume=...) on the same thread; the value becomes the return value of interrupt().
- **Notes:** Before langgraph 0.2.47, Command had no resume parameter, so human input was supplied by editing state with update_state and calling invoke(None, config). Proof: https://github.com/langchain-ai/langgraph/releases/tag/0.2.47

### Evidence Chunks

#### Chunk `f5fb04c45d975bc6` (https://docs.langchain.com/oss/python/langgraph/event-streaming#resume-after-an-interrupt)
**Doc Path:** `event-streaming.mdx` | **Anchor:** `resume-after-an-interrupt`

```text
When a graph pauses for human input, inspect `stream.interrupted` and `stream.interrupts`, then resume by calling `stream_events(..., version="v3")` again with `Command`.

Resume requires a graph compiled with a checkpointer and a config carrying a thread ID — see persistence.

```py
from langgraph.types import Command

stream = graph.stream_events(input, version="v3")

for message in stream.messages:
    print(message.text)

if stream.interrupted:
    print(stream.interrupts)

stream = graph.stream_events(
    Command(resume={"decisions": [{"type": "approve"}]}),
    version="v3",
)
final_state = stream.output
```
```

[ ] verified
Reviewer note:

---

## [q039] How can a node dynamically decide which destination node to trigger next while updating state?

- **Category:** `single`
- **Source:** docs
- **Must mention:** `Command`, `goto`
- **Reference Answer:** Return a Command specifying update to modify state and goto to name the next node.
- **Notes:** Reclassified from version to single: the old '0.2.0' proof page does not mention Command or conditional edges, so no version claim can be supported.

### Evidence Chunks

#### Chunk `6a7f10d0ecdf12d8` (https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately)
**Doc Path:** `thinking-in-langgraph.mdx` | **Anchor:** `handle-errors-appropriately`

```text
Different errors need different handling strategies:

| Error Type | Who Fixes It | Strategy | When to Use |
|------------|--------------|----------|-------------|
| Transient errors (network issues, rate limits) | System (automatic) | Retry policy | Temporary failures that usually resolve on retry |
| LLM-recoverable errors (tool failures, parsing issues) | LLM | Store error in state and loop back | LLM can see the error and adjust its approach |
| User-fixable errors (missing information, unclear instructions) | Human | Pause with `interrupt()` | Need user input to proceed |
| Recoverable failure after retries | Developer (declarative) | `error_handler` | Run a compensation/recovery branch after retry exhaustion |
| Unexpected errors | Developer | Let them bubble up | Unknown issues that need debugging |

Add a retry policy to automatically retry network issues and rate limits.

Combine with `timeout=` to cap each attempt. See Fault tolerance for the full lifecycle.

```python
    from langgraph.types import RetryPolicy

    workflow.add_node(
        "search_documentation",
        search_documentation,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0)
    )
    ```

Store the error in state and loop back so the LLM can see what went wrong and try again:
```

#### Chunk `c638ad2c8a69414b` (https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately)
**Doc Path:** `thinking-in-langgraph.mdx` | **Anchor:** `handle-errors-appropriately`

```text
```python
    from langgraph.types import Command


    def execute_tool(state: State) -> Command[Literal["agent", "execute_tool"]]:
        try:
            result = run_tool(state['tool_call'])
            return Command(update={"tool_result": result}, goto="agent")
        except ToolError as e:
            # Let the LLM see what went wrong and try again
            return Command(
                update={"tool_result": f"Tool error: {str(e)}"},
                goto="agent"
            )
    ```

Pause and collect information from the user when needed (like account IDs, order numbers, or clarifications):

```python
from langgraph.types import Command


def lookup_customer_history(
    state: State,
) -> Command[Literal["lookup_customer_history", "draft_response"]]:
    if not state.get("customer_id"):
        user_input = interrupt(
            {
                "message": "Customer ID needed",
                "request": "Please provide the customer's account ID to look up their subscription history",
            }
        )
        return Command(
            update={"customer_id": user_input["customer_id"]}, goto="lookup_customer_history"
        )
    # Now proceed with the lookup
    customer_data = fetch_customer_history(state["customer_id"])
    return Command(update={"customer_history": customer_data}, goto="draft_response")
    ```

Let them bubble up for debugging. Don't catch what you can't handle:

```python
    def send_reply(state: EmailAgentState):
        try:
            email_service.send(state["draft_response"])
        except Exception:
            raise  # Surface unexpected errors
    ```

After retries are exhausted, run a recovery function that updates state and routes to a compensation branch.
```

#### Chunk `6a63b30c942eddb4` (https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately)
**Doc Path:** `thinking-in-langgraph.mdx` | **Anchor:** `handle-errors-appropriately`

```text
See Fault tolerance for the full pattern.

`error_handler` requires `langgraph>=1.2`.

```python
    from langgraph.errors import NodeError
    from langgraph.types import Command, RetryPolicy

    def payment_error_handler(state: State, error: NodeError) -> Command:
        return Command(
            update={"status": f"compensated: {error.error}"},
            goto="finalize",
        )

    workflow.add_node(
        "charge_payment",
        charge_payment,
        retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
        error_handler=payment_error_handler,
    )
    ```

To apply the same `retry_policy`, `timeout`, or `error_handler` to every node in a graph without repeating them on each `add_node`, use `StateGraph.set_node_defaults(...)`. Per-node values still take precedence. See Fault tolerance.
```

[ ] verified
Reviewer note:

---

## [q040] How can I configure graph-wide retry and error handler defaults across all nodes?

- **Category:** `version`
- **Source:** docs
- **Must mention:** `set_node_defaults`
- **Reference Answer:** Call set_node_defaults on the StateGraph builder to set shared retry_policy, error_handler, timeout or cache_policy for all nodes; per-node values still take precedence.
- **Notes:** Prior to LangGraph 1.2, graph-wide defaults were unavailable and retry_policy had to be repeated on each add_node call. Proof: https://github.com/langchain-ai/langgraph/releases/tag/1.2.0 (feat: add set_node_defaults() to StateGraph, #7747)

### Evidence Chunks

#### Chunk `935b436334202a8a` (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#graph-defaults)
**Doc Path:** `fault-tolerance.mdx` | **Anchor:** `graph-defaults`

```text
Requires `langgraph>=1.2`.


Instead of repeating the same `retry_policy=`, `error_handler=`, `timeout=`, or `cache_policy=` on every `add_node` call, use @[`set_node_defaults`] to configure graph-wide defaults in one place:

```python
from langgraph.errors import NodeError
from langgraph.types import RetryPolicy, TimeoutPolicy
from langgraph.graph import StateGraph, START
from typing_extensions import TypedDict

class State(TypedDict):
    status: str

def default_error_handler(state: State, error: NodeError) -> State:
    return {"status": f"handled: {error.error}"}

graph = (
    StateGraph(State)
    .set_node_defaults(
        retry_policy=RetryPolicy(max_attempts=3),
        error_handler=default_error_handler,
        timeout=TimeoutPolicy(run_timeout=30),
    )
    .add_node("step_a", step_a)
    .add_node("step_b", step_b)
    .add_edge(START, "step_a")
    .compile()
)
```

Both `step_a` and `step_b` now share the same retry policy, error handler, and timeout without any duplication.
```

[ ] verified
Reviewer note:

---

## [q041] How do I attach a dedicated error handler to a node when all retries fail?

- **Category:** `version`
- **Source:** docs
- **Must mention:** `error_handler`, `NodeError`
- **Reference Answer:** Pass error_handler=fn to add_node; fn takes the state and an injected error: NodeError parameter and can return a Command to update state and route elsewhere. It runs only after retries are exhausted.
- **Notes:** Docs for error_handler state 'Requires langgraph>=1.2' (fault-tolerance#error-handling); 1.2.0 release notes mention error-handler resume (#7773). Before 1.2 compensation was done with try/except inside the node. Proof: https://github.com/langchain-ai/langgraph/releases/tag/1.2.0

### Evidence Chunks

#### Chunk `21cf6cebc6be0c62` (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#error-handling)
**Doc Path:** `fault-tolerance.mdx` | **Anchor:** `error-handling`

```text
Requires `langgraph>=1.2`.



An error handler runs after a node fails and all retries are exhausted. It receives the current state and can update it or route to a different node using @[`Command`]. This is useful for compensation flows (Saga patterns) where you want to recover gracefully rather than abort the entire graph.

Pass `error_handler=` to @[`add_node`]:

```python
from langgraph.errors import NodeError
from langgraph.types import Command, RetryPolicy
from langgraph.graph import StateGraph, START
from typing_extensions import TypedDict

class State(TypedDict):
    status: str

def charge_payment(state: State) -> State:
    raise RuntimeError("payment gateway timeout")

def payment_error_handler(state: State, error: NodeError) -> Command:
    return Command(
        update={"status": f"compensated: {error.error}"},
        goto="finalize",
    )

def finalize(state: State) -> State:
    return state

graph = (
    StateGraph(State)
    .add_node(
        "charge_payment",
        charge_payment,
        retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
        error_handler=payment_error_handler,
    )
    .add_node("finalize", finalize)
    .add_edge(START, "charge_payment")
    .compile()
)
```


The handler fires only after the retry policy is exhausted, or immediately if no retry policy is configured. The retry policy and the error handler stay decoupled: configure when to retry and when to compensate independently.
```

#### Chunk `d3cd6f2d08b06df8` (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#nodeerror)
**Doc Path:** `fault-tolerance.mdx` | **Anchor:** `nodeerror`

```text
Error handlers receive failure context through a typed `error: NodeError` parameter, injected by type annotation (the same pattern as `runtime: Runtime`):

```python
from langgraph.errors import NodeError

def my_handler(state: State, error: NodeError) -> Command:
    print(f"Node {error.node} failed with: {error.error}")
    return Command(update={"status": "recovered"}, goto="next_step")
```

@[`NodeError`] is a frozen dataclass with two fields:

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `node` | `str` | Name of the node whose execution failed. |
| `error` | `BaseException` | The exception raised by the failed node. |

The `error: NodeError` parameter is opt-in. Handlers that don't need failure context can use simpler signatures like `(state)` or `(state, runtime)`.
```

[ ] verified
Reviewer note:

---

## [q042] How do I place an execution time limit on an individual node attempt?

- **Category:** `version`
- **Source:** docs
- **Must mention:** `TimeoutPolicy`, `timeout`
- **Reference Answer:** Pass timeout to add_node as seconds, a timedelta, or a TimeoutPolicy (run_timeout / idle_timeout). Timeouts apply only to async nodes.
- **Notes:** Docs state 'Requires langgraph>=1.2' (fault-tolerance#timeouts); before 1.2 add_node had no timeout parameter. Proof: https://github.com/langchain-ai/langgraph/releases/tag/1.2.0 (1.2 line) plus the docs chunk.

### Evidence Chunks

#### Chunk `124b7d2b637c8e75` (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#timeouts)
**Doc Path:** `fault-tolerance.mdx` | **Anchor:** `timeouts`

```text
Requires `langgraph>=1.2`.


The `timeout=` parameter on @[`add_node`] caps how long a single node attempt may run. Pass a number (seconds), a `timedelta`, or a @[`TimeoutPolicy`] for separate run and idle limits:

```python
from datetime import timedelta
from langgraph.types import TimeoutPolicy

# Simple wall-clock cap
builder.add_node("call_model", call_model, timeout=60)
builder.add_node("call_model", call_model, timeout=timedelta(minutes=2))

# Separate run and idle limits
builder.add_node(
    "call_model",
    call_model,
    timeout=TimeoutPolicy(run_timeout=120, idle_timeout=30),
)
```


Node timeouts only apply to **async** nodes. Sync nodes with a `timeout` are rejected at compile time. To wrap blocking I/O, use `asyncio.to_thread` inside an async node.
```

[ ] verified
Reviewer note:

---

## [q043] Which RetryPolicy argument caps the total wall-clock time a node may spend across all of its retry attempts?

- **Category:** `unanswerable`
- **Source:** docs
- **Must mention:** *(None)*
- **Reference Answer:** *(None - Unanswerable)*

### Unanswerability Evidence (Keyword Searches)
Plain-keyword search over chunks.jsonl (2026-10-22): 'max_elapsed' (0 matches), 'deadline' (0 matches), 'total retry' (0 matches), 'retry budget' (0 matches), 'max_delay' (0 matches), 'across all attempts' (0 matches), 'across retries' (2 matches). Rationale: RetryPolicy arguments documented in the corpus (chunk 7fe140ba1e23a918) are max_attempts, initial_interval, backoff_factor, max_interval (which caps delay between retries, not cumulative time), jitter, and retry_on. Per-attempt timeout is configured via add_node(timeout=...) in chunks 124b7d2b637c8e75 and 1ab1471526869a5d where the timeout clock resets on each attempt; no RetryPolicy argument caps total wall-clock time across all attempts. Hits adjudicated irrelevant: 6d61f021e1b376c4, 1b9a02395c8dcdd2.

[ ] verified
Reviewer note:

---

## [q044] Which built-in checkpointer class connects directly to a Neo4j graph database instance?

- **Category:** `unanswerable`
- **Source:** docs
- **Must mention:** *(None)*
- **Reference Answer:** *(None - Unanswerable)*

### Unanswerability Evidence (Keyword Searches)
Plain-keyword search over chunks.jsonl (2026-10-14): 'neo4j' (0 matches). Rationale: Documented checkpointers are InMemory, SQLite, Postgres, MongoDB, and Cosmos DB, with no built-in Neo4j checkpointer. Hits adjudicated irrelevant: none.

[ ] verified
Reviewer note:

---

## [q045] How do I configure raw WebSocket server framing and endpoint handlers in langgraph.json?

- **Category:** `unanswerable`
- **Source:** docs
- **Must mention:** *(None)*
- **Reference Answer:** *(None - Unanswerable)*

### Unanswerability Evidence (Keyword Searches)
Plain-keyword search over chunks.jsonl (2026-10-14): 'websocket' (0 matches), 'web socket' (0 matches), 'socket' (0 matches). Rationale: Documented server transport protocols are HTTP and SSE, with no raw WebSocket framing or handlers. Hits adjudicated irrelevant: none.

[ ] verified
Reviewer note:

---

## [q046] Which InMemorySaver argument caps how many checkpoints are kept per thread?

- **Category:** `unanswerable`
- **Source:** docs
- **Must mention:** *(None)*
- **Reference Answer:** *(None - Unanswerable)*

### Unanswerability Evidence (Keyword Searches)
Plain-keyword search over chunks.jsonl (2026-10-14): 'max_checkpoints' (0 matches), 'retention' (1 matches), 'ttl' (3 matches). Rationale: InMemorySaver stores checkpoints in memory without any retention or checkpoint capping argument. Hits adjudicated irrelevant: 16da86313b94feae, 22ae4759d4f0aa55, 1eabea8372a39087, 485938d00611014a.

[ ] verified
Reviewer note:

---

## [q047] How do I swap in a modified node function on an already-compiled graph without recompiling it?

- **Category:** `unanswerable`
- **Source:** docs
- **Must mention:** *(None)*
- **Reference Answer:** *(None - Unanswerable)*

### Unanswerability Evidence (Keyword Searches)
Plain-keyword search over chunks.jsonl (2026-10-14): 'hot swap' (0 matches), 'hot-swap' (0 matches), 'replace node' (0 matches), 'reload' (0 matches). Rationale: Compiled graphs are immutable structures with no support for swapping node functions without recompilation. Hits adjudicated irrelevant: none.

[ ] verified
Reviewer note:

---

## [q048] How do I export an existing StateGraph definition into a GraphQL mutation schema?

- **Category:** `unanswerable`
- **Source:** docs
- **Must mention:** *(None)*
- **Reference Answer:** *(None - Unanswerable)*

### Unanswerability Evidence (Keyword Searches)
Plain-keyword search over chunks.jsonl (2026-10-14): 'graphql' (0 matches). Rationale: LangGraph provides no GraphQL schema generation or mutation export capabilities. Hits adjudicated irrelevant: none.

[ ] verified
Reviewer note:

---

## [q049] Which setting runs each graph node in its own Kubernetes Pod?

- **Category:** `unanswerable`
- **Source:** docs
- **Must mention:** *(None)*
- **Reference Answer:** *(None - Unanswerable)*

### Unanswerability Evidence (Keyword Searches)
Plain-keyword search over chunks.jsonl (2026-10-14): 'kubernetes' (0 matches), 'k8s' (0 matches), 'pod' (0 matches), 'pods' (0 matches), 'executor' (0 matches). Rationale: Graph nodes execute in-process and there is no executor backend for scheduling individual nodes as Kubernetes pods. Hits adjudicated irrelevant: none.

[ ] verified
Reviewer note:

---

## [q050] How do I track dollar cost and token billing per node attempt using execution_info?

- **Category:** `unanswerable`
- **Source:** docs
- **Must mention:** *(None)*
- **Reference Answer:** *(None - Unanswerable)*

### Unanswerability Evidence (Keyword Searches)
Plain-keyword search over chunks.jsonl (2026-10-14): 'billing' (5 matches), 'cost' (4 matches), 'token usage' (2 matches), 'dollar' (0 matches). Rationale: The execution_info runtime object exposes retry and tracing metadata only, with no dollar cost or token billing attributes. Hits adjudicated irrelevant: 8910a2ee2e6eceae, 9f8b395e2fca69e3, b16ab7e8fc45f76f, f9f8d48e79be1134, 88b3b001108649f3, f0cfdf3abbe906d0, b4199820f7d508c6, 24e76416b458ca31, 485938d00611014a, e2bc10ee4e354945.

[ ] verified
Reviewer note:

---
