# Judge audit

Run: results/runs/baseline-20261116-1050
Judge: gemini-3.5-flash-lite, prompt version 1 (judge_v1.jsonl)

Selection: 10 items drawn per category with seed 21, plus every
other judged item with judge correctness below 2 (stratification by
judge score, not a redraw), flagged in the selection column.

Fill the three human columns. correctness: 2 = agrees with the reference on every
key fact with the right API names; 1 = partly correct or incomplete, nothing
contradicts the reference; 0 = wrong, contradicts the reference, or outdated or
invented API. citation_support: 1 = every CITED excerpt supports a claim and no
central claim lacks a CITED excerpt. faithful: every claim is supported by the
excerpts (used in M09 to sanity-check RAGAS faithfulness).

| # | id | category | selection | judge correctness | judge citation_support | human correctness (0/1/2) | human citation_support (0/1) | faithful (yes/no) |
|---|---|---|---|---|---|---|---|---|
| 1 | q006 | single | seed 21 | 2 | 0 | 2 | 1 | yes |
| 2 | q012 | single | seed 21 | 2 | 1 | 2 | 1 | yes |
| 3 | q016 | single | seed 21 | 2 | 1 | 2 | 1 | no |
| 4 | q023 | single | seed 21 | 2 | 1 | 2 | 1 | yes |
| 5 | q026 | single | seed 21 | 2 | 1 | 2 | 1 | yes |
| 6 | q028 | single | seed 21 | 2 | 1 | 2 | 1 | yes |
| 7 | q031 | multi | seed 21 | 2 | 1 | 1 | 1 | yes |
| 8 | q033 | multi | seed 21 | 2 | 1 | 2 | 1 | no |
| 9 | q040 | version | seed 21 | 2 | 1 | 2 | 1 | yes |
| 10 | q041 | version | seed 21 | 2 | 1 | 2 | 1 | yes |
| 11 | q024 | single | added: judge score < 2 | 1 | 1 | 1 | 1 | no |

## 1. q006 (single; seed 21)

**Question:** What method lets an operator overwrite state attributes on an existing thread without running a node?

**Reference answer:** Call update_state(config, values). It creates a new checkpoint (the original is not modified) and passes values through reducers like a node update.

**must_mention:** update_state

**Answer:**

Use the graph's `update_state` method. It lets an operator edit the thread's state and creates a new checkpoint without running any node.

**Excerpts (context order):**

[1] NOT CITED Use the graph API > Define and update state > Bypass reducers with `Overwrite` (https://docs.langchain.com/oss/python/langgraph/use-graph-api#bypass-reducers-with-overwrite)

```text
In some cases, you may want to bypass a reducer and directly overwrite a state value. LangGraph provides the `Overwrite` type for this purpose. When a node returns a value wrapped with `Overwrite`, the reducer is bypassed and the channel is set directly to that value.

This is useful when you want to reset or replace accumulated state rather than merge it with existing values.

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Overwrite
from typing_extensions import Annotated, TypedDict
import operator

class State(TypedDict):
    messages: Annotated[list, operator.add]

def add_message(state: State):
    return {"messages": ["first message"]}

def replace_messages(state: State):
    # Bypass the reducer and replace the entire messages list
    return {"messages": Overwrite(["replacement message"])}

builder = StateGraph(State)
builder.add_node("add_message", add_message)
builder.add_node("replace_messages", replace_messages)
builder.add_edge(START, "add_message")
builder.add_edge("add_message", "replace_messages")
builder.add_edge("replace_messages", END)

graph = builder.compile()

result = graph.invoke({"messages": ["initial"]})
print(result["messages"])
```

```
['replacement message']
```

You can also use JSON format with the special key `"__overwrite__"`:

```python
def replace_messages(state: State):
    return {"messages": {"__overwrite__": ["replacement message"]}}
```


When nodes execute in parallel, only one node can use `Overwrite` on the same state key in a given super-step. If multiple nodes attempt to overwrite the same key in the same super-step, an `InvalidUpdateError` will be raised.
```

[2] CITED Checkpointers > Get and update state > Update state (https://docs.langchain.com/oss/python/langgraph/checkpointers#update-state)

```text
You can edit the graph state using @`update_state`]. This creates a new checkpoint with the updated values — it does not modify the original checkpoint. The update is treated the same as a node update: values are passed through [reducer functions when defined, so channels with reducers _accumulate_ values rather than overwrite them.

You can optionally specify `as_node` to control which node the update is treated as coming from, which affects which node executes next. See Time travel: `as_node` for details.
```

[3] NOT CITED Graph API overview > State > Working with messages in graph state (https://docs.langchain.com/oss/python/langgraph/graph-api#working-with-messages-in-graph-state)

```text
#### Why use messages?

Most modern LLM providers have a chat model interface that accepts a list of messages as input. LangChain's chat model interface in particular accepts a list of message objects as inputs. These messages come in a variety of forms such as @[`HumanMessage`] (user input) or @[`AIMessage`] (LLM response).

To read more about what message objects are, please refer to the Messages conceptual guide.

#### Using messages in your graph

In many cases, it is helpful to store prior conversation history as a list of messages in your graph state. To do so, we can add a key (channel) to the graph state that stores a list of `Message` objects and annotate it with a reducer function (see `messages` key in the example below). The reducer function is vital to telling the graph how to update the list of `Message` objects in the state with each state update (for example, when a node sends an update). If you don't specify a reducer, every state update will overwrite the list of messages with the most recently provided value. If you wanted to simply append messages to the existing list, you could use `operator.add` as a reducer.

However, you might also want to manually update messages in your graph state (e.g. human-in-the-loop). If you were to use `operator.add`, the manual state updates you send to the graph would be appended to the existing list of messages, instead of updating existing messages. To avoid that, you need a reducer that can keep track of message IDs and overwrite existing messages, if updated. To achieve this, you can use the prebuilt @[`add_messages`] function. For brand new messages, it will simply append to existing list, but it will also handle the updates for existing messages correctly.

#### Serialization
```

[4] NOT CITED Use time-travel > Fork > From a specific node (https://docs.langchain.com/oss/python/langgraph/use-time-travel#from-a-specific-node)

```text
When you call @`update_state`], values are applied using the specified node's writers (including [reducers). The checkpoint records that node as having produced the update, and execution resumes from that node's successors.

By default, LangGraph infers `as_node` from the checkpoint's version history. When forking from a specific checkpoint, this inference is almost always correct.

Specify `as_node` explicitly when:

- **Parallel branches**: Multiple nodes updated state in the same step, and LangGraph can't determine which was last (`InvalidUpdateError`).
- **No execution history**: Setting up state on a fresh thread (common in testing).
- **Skipping nodes**: Set `as_node` to a later node to make the graph think that node already ran.

```python
# graph: generate_topic -> write_joke

# Treat this update as if generate_topic produced it.
# Execution resumes at write_joke (the successor of generate_topic).
fork_config = graph.update_state(
    before_joke.config,
    values={"topic": "chickens"},
    as_node="generate_topic",
)
```
```

[5] NOT CITED Graph API overview > State > Reducers (https://docs.langchain.com/oss/python/langgraph/graph-api#reducers)

```text
`{"foo": 1, "bar": ["hi"]}`. Let's then assume the first `Node` returns `{"foo": 2}`. This is treated as an update to the state. Notice that the `Node` does not need to return the whole `State` schema - just an update. After applying this update, the `State` would then be `{"foo": 2, "bar": ["hi"]}`. If the second node returns `{"bar": ["bye"]}` then the `State` would then be `{"foo": 2, "bar": ["bye"]}`

#### Custom reducers

A custom reducer combines the left and right arguments instead of replacing the state value, which is useful for accumulating values, such as appending updates to a list. This example shows how to specify a custom reducer:

In this example, we've used the `Annotated` type to specify a reducer function (`operator.add`) for the second key (`bar`). Note that the first key remains unchanged. Let's assume the input to the graph is `{"foo": 1, "bar": ["hi"]}`. Let's then assume the first `Node` returns `{"foo": 2}`. This is treated as an update to the state. Notice that the `Node` does not need to return the whole `State` schema - just an update. After applying this update, the `State` would then be `{"foo": 2, "bar": ["hi"]}`. If the second node returns `{"bar": ["bye"]}` then the `State` would then be `{"foo": 2, "bar": ["hi", "bye"]}`. Notice here that the `bar` key is updated by adding the two lists together.

#### Overwrite

In some cases, you may want to bypass a reducer and directly overwrite a state value. LangGraph provides the `Overwrite` type for this purpose. Learn how to use `Overwrite` here.

#### Resetting a reducer field
```

**Judge verdict:** correctness=2, citation_support=0

**Judge rationale:** The assistant correctly identified update_state and its functionality, matching the reference answer. However, it did not provide any citations from the excerpts, so citation_support is 0.

## 2. q012 (single; seed 21)

**Question:** Which built-in state class gives me a messages list out of the box?

**Reference answer:** MessagesState, which stores a messages list of chat messages.

**must_mention:** MessagesState

**Answer:**

The built‑in state class that provides a ready‑made list of messages is `MessagesState`. It defines a single `messages` key as a list of `AnyMessage` objects and uses the `@add_messages` reducer.

**Excerpts (context order):**

[1] CITED Graph API overview > State > Working with messages in graph state (https://docs.langchain.com/oss/python/langgraph/graph-api#working-with-messages-in-graph-state)

```text
In addition to keeping track of message IDs, the @[`add_messages`] function will also try to deserialize messages into LangChain `Message` objects whenever a state update is received on the `messages` channel.

For more information, see LangChain serialization/deserialization. This allows sending graph inputs / state updates in the following format:

```python
# this is supported
{"messages": [HumanMessage(content="message")]}

# and this is also supported
{"messages": [{"type": "human", "content": "message"}]}
```

Since the state updates are always deserialized into LangChain `Messages` when using @[`add_messages`], you should use dot notation to access message attributes, like `state["messages"][-1].content`.

Below is an example of a graph that uses @[`add_messages`] as its reducer function.

```python
from langchain.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict

class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

#### MessagesState

Since having a list of messages in your state is so common, there exists a prebuilt state called `MessagesState` which makes it easy to use messages. `MessagesState` is defined with a single `messages` key which is a list of `AnyMessage` objects and uses the @[`add_messages`] reducer. Typically, there is more state to track than just messages, so we see people subclass this state and add more fields, like:

```python
from langgraph.graph import MessagesState

class State(MessagesState):
    documents: list[str]
```
```

[2] NOT CITED Quickstart > 2. Define state (https://docs.langchain.com/oss/python/langgraph/quickstart#2-define-state)

```text
The graph's state is used to store the messages and the number of LLM calls.



    State in LangGraph persists throughout the agent's execution.

    The `Annotated` type with `operator.add` ensures that new messages are appended to the existing list rather than replacing it.





```python
from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
```
```

[3] NOT CITED Use the graph API > Define and update state > Process state updates with reducers (https://docs.langchain.com/oss/python/langgraph/use-graph-api#process-state-updates-with-reducers)

```text
Each key in the state can have its own independent reducer function, which controls how updates from nodes are applied. If no reducer function is explicitly specified then it is assumed that all updates to the key should override it.

For `TypedDict` state schemas, we can define reducers by annotating the corresponding field of the state with a reducer function.

In the earlier example, our node updated the `"messages"` key in the state by appending a message to it. Below, we add a reducer to this key, such that updates are automatically appended:

```python
from typing_extensions import Annotated

def add(left, right):
    """Can also import `add` from the `operator` built-in."""
    return left + right

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add]  # [!code highlight]
    extra_field: int
```

Now our node can be simplified:

```python
def node(state: State):
    new_message = AIMessage("Hello!")
    return {"messages": [new_message], "extra_field": 10}  # [!code highlight]
```

```python
from langgraph.graph import START

graph = StateGraph(State).add_node(node).add_edge(START, "node").compile()

result = graph.invoke({"messages": [HumanMessage("Hi")]})

for message in result["messages"]:
    message.pretty_print()
```

```
================================ Human Message ================================

Hi
================================== Ai Message ==================================

Hello!
```

#### MessagesState

In practice, there are additional considerations for updating lists of messages:

* We may wish to update an existing message in the state.
* We may want to accept short-hands for message formats, such as OpenAI format.

LangGraph includes a built-in reducer @[`add_messages`] that handles these considerations:
```

[4] NOT CITED Use the graph API > Define and update state > Define state (https://docs.langchain.com/oss/python/langgraph/use-graph-api#define-state)

```text
State in LangGraph can be a `TypedDict`, `Pydantic` model, or dataclass. Below we will use `TypedDict`. See Use Pydantic models for graph state for detail on using Pydantic.


By default, graphs will have the same input and output schema, and the state determines that schema. See Define input and output schemas for how to define distinct input and output schemas.

Let's consider a simple example using messages. This represents a versatile formulation of state for many LLM applications. See our concepts page for more detail.

```python
from langchain.messages import AnyMessage
from typing_extensions import TypedDict

class State(TypedDict):
    messages: list[AnyMessage]
    extra_field: int
```

This state tracks a list of message objects, as well as an extra integer field.
```

[5] NOT CITED Subgraphs > Subgraph persistence > Stateful (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#stateful)

```text
State accumulates across invocations—the subagent remembers past conversations:

```python
  config = {"configurable": {"thread_id": "1"}}

  # First call
  response = agent.invoke(
      {"messages": [{"role": "user", "content": "Tell me about apples"}]},
      config=config,
  )
  # Subagent message count: 4

  # Second call - subagent REMEMBERS apples conversation
  response = agent.invoke(
      {"messages": [{"role": "user", "content": "Now tell me about bananas"}]},
      config=config,
  )
  # Subagent message count: 8 (accumulated!)
  ```

When you have multiple **different** per-thread subgraphs (for example, a fruit expert and a veggie expert), each one needs its own storage space so their checkpoints don't overwrite each other. This is called **namespace isolation**.

If you call subgraphs inside a node, LangGraph assigns namespaces based on call order (first call, second call, etc.). This means reordering your calls can mix up which subgraph loads which state. To avoid this, wrap each subagent in its own `StateGraph` with a unique node name—this gives each subgraph a stable, unique namespace:
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant correctly identifies MessagesState, details its messages key and add_messages reducer, supported directly by excerpt 1.

## 3. q016 (single; seed 21)

**Question:** How can I retrieve stored memories by semantic similarity rather than exact key match?

**Reference answer:** Configure the store with an embedding index, then call store.search(namespace, query="...", limit=N) with a natural-language query.

**must_mention:** store.search

**Answer:**

Enable semantic search on the memory store by creating an InMemoryStore with an embedding index, then use store.search with a natural‑language query. The store embeds the query and returns the most similar memories.
```python
from langchain.embeddings import init_embeddings
from langgraph.store.memory import InMemoryStore

# Create a store that can perform semantic search
store = InMemoryStore(
 index={
 "embed": init_embeddings("openai:text-embedding-3-small"),
 "dims": 1536,
 }
)

# Store some memories (you can limit which fields are embedded)
store.put(("user_123", "memories"), "1", {"text": "I love pizza"})
store.put(("user_123", "memories"), "2", {"text": "I am a plumber"})

# Retrieve by semantic similarity instead of exact key
items = store.search(("user_123", "memories"), query="I'm hungry", limit=1)
print(items.value["text"]) # → "I love pizza"
```

**Excerpts (context order):**

[1] CITED Stores > Semantic search (https://docs.langchain.com/oss/python/langgraph/stores#semantic-search)

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
    limit=3  # Return top 3 matches
)
```


You can control which parts of your memories get embedded by configuring the `fields` parameter or by specifying the `index` parameter when storing memories:

```python
# Store with specific fields to embed
store.put(
    namespace_for_memory,
    str(uuid7()),
    {
        "food_preference": "I love Italian cuisine",
        "context": "Discussing dinner plans"
    },
    index=["food_preference"]  # Only embed "food_preferences" field
)

# Store without embedding (still retrievable, but not searchable)
store.put(
    namespace_for_memory,
    str(uuid7()),
    {"system_info": "Last updated: 2024-01-01"},
    index=False
)
```
```

[2] CITED Memory > Add long-term memory > Use semantic search (https://docs.langchain.com/oss/python/langgraph/add-memory#use-semantic-search)

```text
Enable semantic search in your graph's memory store to let graph agents search for items in the store by semantic similarity.

```python
from langchain.embeddings import init_embeddings
from langgraph.store.memory import InMemoryStore

# Create store with semantic search enabled
embeddings = init_embeddings("openai:text-embedding-3-small")
store = InMemoryStore(
    index={
        "embed": embeddings,
        "dims": 1536,
    }
)

store.put(("user_123", "memories"), "1", {"text": "I love pizza"})
store.put(("user_123", "memories"), "2", {"text": "I am a plumber"})

items = store.search(
    ("user_123", "memories"), query="I'm hungry", limit=1
)
```
```

[3] NOT CITED Memory > Add long-term memory > Use semantic search (https://docs.langchain.com/oss/python/langgraph/add-memory#use-semantic-search)

```text
```python

    from langchain.embeddings import init_embeddings
    from langchain.chat_models import init_chat_model
    from langgraph.store.memory import InMemoryStore
    from langgraph.graph import START, MessagesState, StateGraph
    from langgraph.runtime import Runtime  # [!code highlight]

    model = init_chat_model("gpt-5.4-mini")

    # Create store with semantic search enabled
    embeddings = init_embeddings("openai:text-embedding-3-small")
    store = InMemoryStore(
        index={
            "embed": embeddings,
            "dims": 1536,
        }
    )

    store.put(("user_123", "memories"), "1", {"text": "I love pizza"})
    store.put(("user_123", "memories"), "2", {"text": "I am a plumber"})

    async def chat(state: MessagesState, runtime: Runtime):  # [!code highlight]
        # Search based on user's last message
        items = await runtime.store.asearch(  # [!code highlight]
            ("user_123", "memories"), query=state["messages"][-1].content, limit=2
        )
        memories = "\n".join(item.value["text"] for item in items)
        memories = f"## Memories of user\n{memories}" if memories else ""
        response = await model.ainvoke(
            [
                {"role": "system", "content": f"You are a helpful assistant.\n{memories}"},
                *state["messages"],
            ]
        )
        return {"messages": [response]}


    builder = StateGraph(MessagesState)
    builder.add_node(chat)
    builder.add_edge(START, "chat")
    graph = builder.compile(store=store)

    stream = await graph.astream_events(
        {"messages": [{"role": "user", "content": "I'm hungry"}]},
        version="v3",
    )
    async for message in stream.messages:
        async for token in message.text:
            print(token, end="", flush=True)
    ```
```

[4] NOT CITED Stores > Listing items in a namespace (https://docs.langchain.com/oss/python/langgraph/stores#listing-items-in-a-namespace)

```text
Calling `store.search` (or the async `store.asearch`) with no `query` and no `filter` returns the items stored under `namespace_prefix`, up to `limit`. Use this to enumerate everything in a namespace when you don't need semantic ranking.







Three behaviors to keep in mind:

- **`namespace_prefix` matches by prefix, not exactly.** `("alice",)` also returns items under `("alice", "memories")`, `("alice", "preferences")`, and so on. To restrict to a single level, pass the full namespace or filter the returned items client-side on `item.namespace`.
- **Results past `limit` are silently truncated.** There is no overflow signal—set `limit` above your expected maximum, or paginate with `offset`.
- **Default ordering depends on the store backend.** `PostgresStore` and `AsyncPostgresStore` return results ordered by `updated_at` descending (most recently updated first). `InMemoryStore` returns results in insertion order (most recently inserted last). Do not rely on a specific order across implementations; sort client-side on `item.updated_at` if order matters.

To page through a large namespace:





To discover which namespaces exist (for example, to iterate over every user before listing their memories), use `store.list_namespaces` or `store.alist_namespaces`:
```

[5] NOT CITED Stores > Build a custom store > Semantic search support (https://docs.langchain.com/oss/python/langgraph/stores#semantic-search-support)

```text
Store values are plain Python dicts — no special serializer is required. Serialize with `json.dumps` / `json.loads` or a JSONB column directly. Do not store raw Python objects that are not JSON-serializable.

If your backend supports vector search, implement the `query` parameter on `asearch`:

- Accept a `query: str | None` argument.
- When `query` is not `None`, embed it and rank results by cosine similarity.
- Results should include a `score` field on each `Item` when `query` is provided.

If your backend does not support vector search, raise `NotImplementedError` when `query` is passed.
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant correctly explains configuring the store with an embedding index and using store.search with a query, backed by cited excerpt 2.

## 4. q023 (single; seed 21)

**Question:** How do you ensure state schema changes remain compatible with existing thread checkpoints?

**Reference answer:** Add new state fields as NotRequired (or Optional with a None default) so old checkpoints still validate.

**must_mention:** NotRequired

**Answer:**

To keep state schema changes compatible with existing checkpoints, add any new fields as optional (e.g., `NotRequired` or `Optional[...] = None`) so older snapshots still validate. Treat removals as deprecations: keep the field in the TypedDict for at least one drain cycle, even if no node reads it, and later remove it after confirming no in‑flight threads depend on it. For renames, use an add‑then‑remove approach—add the new key alongside the old one, write to both during a transition window, then drop the old key. Ensure node functions ignore unknown keys, and use `graph.get_state` or `graph.get_state_history` in a staging deployment to spot‑check threads before rolling out. Avoid tightening required fields or changing types in ways that would invalidate existing snapshots, as such changes can break resumed runs.

**Excerpts (context order):**

[1] NOT CITED Backward compatibility (https://docs.langchain.com/oss/python/langgraph/backward-compatibility)

```text
Software needs to change in production. New requirements, bug fixes, and refactors all eventually land in your graph code. Because LangGraph runs the latest deployed graph against state that has been persisted for existing threads, every change you ship is effectively a backward-compatible API change with respect to your existing checkpoints.

Unlike workflow engines that pin a run to the version of code it started with, LangGraph applies the latest graph immediately to *every* thread, both new threads and threads that resume from a checkpoint. This is convenient: bug fixes propagate to in-flight conversations and agents without ceremony. It also means you must reason about how each change interacts with runs that started under the previous version of the code.

There are three categories of compatibility issues to watch for, in roughly the order you will encounter them:

1. Technical compatibility: The most common; the new code must still load and execute against existing State.
2. Business compatibility: Less common; existing runs should keep following the old business logic even though the code has changed.
3. Non-determinism: Only applies to the Functional API.


For a short summary of which graph topology and state changes the runtime supports by default, see Graph migrations. The rest of this page covers the patterns you can apply when a change falls outside that supported set.
```

[2] CITED Backward compatibility > Technical compatibility > Recommended patterns (https://docs.langchain.com/oss/python/langgraph/backward-compatibility#recommended-patterns)

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

[3] CITED Backward compatibility > Technical compatibility (https://docs.langchain.com/oss/python/langgraph/backward-compatibility#technical-compatibility)

```text
Technical compatibility is the equivalent of an API breaking change in a microservice. The "API" here is the contract between your graph code and the data already persisted by the checkpointer for existing threads. When a thread resumes, LangGraph deserializes the saved state, dispatches it to a node by name, and expects the node to return values that fit the state schema.

Common technical breakages:

- **Renaming or removing a node** while threads are paused at or about to enter that node, for example at an @[`interrupt`] or via a checkpointed conditional edge that still routes to the old name. On resume, LangGraph cannot find the node by its saved name and the run fails. The starting point for resuming a run is the beginning of the node where execution stopped, so a missing node has nowhere to resume from.
- **Renaming or removing a State key** that older checkpoints still contain or that downstream nodes still read.
- **Tightening a State field**, such as making an `Optional` field required, narrowing a type, or adding a new required field with no default. Existing checkpoints will not satisfy the new schema.

Edge topology itself is *not* persisted in the checkpoint. Adding, removing, or rerouting edges between nodes that still exist is safe for in-flight threads. Per the Graph migrations summary, the only topology change that can break an interrupted thread is renaming or removing a node.
```

[4] CITED Graph API overview > Graph migrations (https://docs.langchain.com/oss/python/langgraph/graph-api#graph-migrations)

```text
LangGraph can easily handle migrations of graph definitions (nodes, edges, and state) even when using a checkpointer to track state.

- For threads at the end of the graph (i.e. not interrupted) you can change the entire topology of the graph (i.e. all nodes and edges, remove, add, rename, etc)
- For threads currently interrupted, we support all topology changes other than renaming / removing nodes (as that thread could now be about to enter a node that no longer exists) -- if this is a blocker please reach out and we can prioritize a solution.
- For modifying state, we have full backwards and forwards compatibility for adding and removing keys
- State keys that are renamed lose their saved state in existing threads
- State keys whose types change in incompatible ways could currently cause issues in threads with state from before the change -- if this is a blocker please reach out and we can prioritize a solution.


For changes that are technically compatible but alter business logic, such as rewriting the tool set or restructuring conversation flow, see Business compatibility. That page covers pinning a behavioral version in state so existing threads keep the old path while new threads pick up the latest version.
```

[5] NOT CITED Checkpointers > Get and update state > Get state history (https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state-history)

```text
You can get the full history of the graph execution for a given thread by calling @[`graph.get_state_history(config)`][get_state_history]. This will return a list of `StateSnapshot` objects associated with the thread ID provided in the config. Importantly, the checkpoints will be ordered chronologically with the most recent checkpoint / `StateSnapshot` being the first in the list.

```python
config = {"configurable": {"thread_id": "1"}}
list(graph.get_state_history(config))
```

In this example, the output of @[`get_state_history`] will look like this:
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant correctly details how to ensure compatibility by adding new fields as NotRequired or Optional, handling removals, renames, and spot-checking, fully supported by the cited documentation.

## 5. q026 (single; seed 21)

**Question:** How can I invoke and test a specific isolated node from a compiled graph?

**Reference answer:** Access it through compiled_graph.nodes (e.g. compiled_graph.nodes["node1"]) and call invoke() with test input; this bypasses any checkpointer.

**must_mention:** nodes

**Answer:**

Compile the graph as usual and then call the desired node directly through the compiled graph’s `nodes` mapping, which holds a reference to each node. Invoking the node this way bypasses any checkpointer logic and lets you test the node in isolation. Example:
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

def create_graph() -> StateGraph:
 class MyState(TypedDict):
 my_key: str
 g = StateGraph(MyState)
 g.add_node("node1", lambda s: {"my_key": "hello from node1"})
 g.add_edge(START, "node1")
 g.add_edge("node1", END)
 return g

checkpointer = MemorySaver()
graph = create_graph()
compiled = graph.compile(checkpointer=checkpointer)
# Invoke only node1
result = compiled.nodes["node1"].invoke({"my_key": "initial_value"})
assert result["my_key"] == "hello from node1"
```[1]

**Excerpts (context order):**

[1] CITED Test > Testing individual nodes and edges (https://docs.langchain.com/oss/python/langgraph/test#testing-individual-nodes-and-edges)

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

[2] NOT CITED Test > Partial execution (https://docs.langchain.com/oss/python/langgraph/test#partial-execution)

```text
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
    graph.add_node("node3", lambda state: {"my_key": "hello from node3"})
    graph.add_node("node4", lambda state: {"my_key": "hello from node4"})
    graph.add_edge(START, "node1")
    graph.add_edge("node1", "node2")
    graph.add_edge("node2", "node3")
    graph.add_edge("node3", "node4")
    graph.add_edge("node4", END)
    return graph

def test_partial_execution_from_node2_to_node3() -> None:
    checkpointer = MemorySaver()
    graph = create_graph()
    compiled_graph = graph.compile(checkpointer=checkpointer)
    compiled_graph.update_state(
        config={
          "configurable": {
            "thread_id": "1"
          }
        },
        # The state passed into node 2 - simulating the state at
        # the end of node 1
        values={"my_key": "initial_value"},
        # Update saved state as if it came from node 1
        # Execution will resume at node 2
        as_node="node1",
    )
    result = compiled_graph.invoke(
        # Resume execution by passing None
        None,
        config={"configurable": {"thread_id": "1"}},
        # Stop after node 3 so that node 4 doesn't run
        interrupt_after="node3",
    )
    assert result["my_key"] == "hello from node3"
```
```

[3] NOT CITED Test > Partial execution (https://docs.langchain.com/oss/python/langgraph/test#partial-execution)

```text
For agents made up of larger graphs, you may wish to test partial execution paths within your agent rather than the entire flow end-to-end. In some cases, it may make semantic sense to restructure these sections as subgraphs, which you can invoke in isolation as normal.

However, if you do not wish to make changes to your agent graph's overall structure, you can use LangGraph's persistence mechanisms to simulate a state where your agent is paused right before the beginning of the desired section, and will pause again at the end of the desired section. The steps are as follows:

1. Compile your agent with a checkpointer (the in-memory checkpointer @[`InMemorySaver`] will suffice for testing).
2. Call your agent's `update_state` method with an `as_node` parameter set to the name of the node *before* the one you want to start your test.
3. Invoke your agent with the same `thread_id` you used to update the state and an `interrupt_after` parameter set to the name of the node you want to stop at.

Here's an example that executes only the second and third nodes in a linear graph:
```

[4] NOT CITED Use time-travel > Replay (https://docs.langchain.com/oss/python/langgraph/use-time-travel#replay)

```text
Invoke the graph with a prior checkpoint's config to replay from that point.

Replay re-executes nodes—it doesn't just read from cache. LLM calls, API requests, and interrupts fire again and may return different results. Replaying from the final checkpoint (no `next` nodes) is a no-op.

Use @[`get_state_history`] to find the checkpoint you want to replay from, then call @[`invoke`][CompiledStateGraph.invoke] with that checkpoint's config:
```

[5] NOT CITED Test > Getting started (https://docs.langchain.com/oss/python/langgraph/test#getting-started)

```text
First, make sure you have `pytest` installed:

```bash
$ pip install -U pytest
```

Because many LangGraph agents depend on state, a useful pattern is to create your graph before each test where you use it, then compile it within tests with a new checkpointer instance.

The below example shows how this works with a simple, linear graph that progresses through `node1` and `node2`. Each node updates the single state key `my_key`:

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

def test_basic_agent_execution() -> None:
    checkpointer = MemorySaver()
    graph = create_graph()
    compiled_graph = graph.compile(checkpointer=checkpointer)
    result = compiled_graph.invoke(
        {"my_key": "initial_value"},
        config={"configurable": {"thread_id": "1"}}
    )
    assert result["my_key"] == "hello from node2"
```
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant correctly explains accessing nodes via compiled_graph.nodes and invoking them in isolation, perfectly matching the reference answer and supported by the cited excerpt.

## 6. q028 (single; seed 21)

**Question:** In Pregel, which channel is used by default, and what happens to earlier values?

**Reference answer:** LastValue is the default channel type; it stores the last value written and overwrites any previous value.

**must_mention:** LastValue

**Answer:**

Pregel uses the `LastValue` channel by default. This channel stores the last value written, overwriting any earlier values.[4]

**Excerpts (context order):**

[1] NOT CITED LangGraph runtime > Channels (https://docs.langchain.com/oss/python/langgraph/pregel#channels)

```text
An **actor** is a `PregelNode`. It subscribes to channels, reads data from them, and writes data to them. It can be thought of as an **actor** in the Pregel algorithm. `PregelNodes` implement LangChain's Runnable interface.

Channels are used to communicate between actors (PregelNodes). Each channel has a value type, an update type, and an update function—which takes a sequence of updates and modifies the stored value. Channels can be used to send data from one chain to another, or to send data from a chain to itself in a future step.
```

[2] NOT CITED LangGraph runtime > Channels > DeltaChannel (https://docs.langchain.com/oss/python/langgraph/pregel#deltachannel)

```text
```python
from typing import Any, Sequence


# List: append all writes in order
def list_reducer(state: list[Any], writes: Sequence[list[Any]]) -> list[Any]:
    result = list(state)
    for write in writes:
        result.extend(write)
    return result


# Dict: merge all writes, last write wins on key conflicts
def dict_reducer(
    state: dict[str, Any], writes: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    result = dict(state)
    for write in writes:
        result.update(write)
    return result
```

Both are associative: applying batches one at a time produces the same result as applying them together.

#### Use snapshot_frequency for bounded read latency

Without snapshots, reading a `DeltaChannel` value requires replaying the full write history—O(N) for a thread with N steps. Setting `snapshot_frequency=K` writes a full snapshot every K pregel steps, bounding read depth to at most K steps:

```python
class State(TypedDict):
    messages: Annotated[
        list[str],
        DeltaChannel(my_reducer, snapshot_frequency=5),
    ]
```

Higher values of `snapshot_frequency` reduce storage overhead but increase read latency. Lower values bound latency more tightly at the cost of larger checkpoints. `None` (the default) skips snapshots entirely—appropriate when reads are rare or threads are short.

#### Version compatibility and rollbacks

Changing a persisted channel from `DeltaChannel` to a non-delta channel is not recommended. Checkpoints encode these channel types differently, so changing the type for an existing thread can cause incomplete or incorrect state reconstruction. Keep channel definitions stable for the lifetime of a thread. Before changing a channel type, migrate affected threads to the new representation, or discard them and start new threads.
```

[3] NOT CITED Event streaming > Channels and event lifecycle (https://docs.langchain.com/oss/python/langgraph/event-streaming#channels-and-event-lifecycle)

```text
Raw events flow on channels. The channel name appears as the event's `method`; each channel emits a specific event shape.

| Channel | Purpose |
| ------- | ------- |
| `values` | Full graph state snapshots. |
| `updates` | Per-node state deltas. |
| `messages` | Content-block-centric chat model output. |
| `tools` | Tool call start, streamed output, finish, and error events. |
| `lifecycle` | Run, subgraph, and subagent status changes. |
| `checkpoints` | Lightweight checkpoint envelopes for branching and time travel. |
| `input` | Human-in-the-loop input requests and responses. |
| `tasks` | Pregel task creation and result events. |
| `custom` | User-defined payloads from graph code. |
| `custom:` | Application-defined stream transformer output. |

The typed projections (`stream.messages`, `stream.values`, etc.) are built from these channels. The channel name appears as the `method` field on raw events when you iterate the run object directly.
```

[4] CITED LangGraph runtime > Channels > Topic (https://docs.langchain.com/oss/python/langgraph/pregel#topic)

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

[5] NOT CITED LangGraph runtime > Overview (https://docs.langchain.com/oss/python/langgraph/pregel#overview)

```text
In LangGraph, Pregel combines **actors** and **channels** into a single application. **Actors** read data from channels and write data to channels. Pregel organizes the execution of the application into multiple steps, following the **Pregel Algorithm**/**Bulk Synchronous Parallel** model.

Each step consists of three phases:

* **Plan**: Determine which **actors** to execute in this step. For example, in the first step, select the **actors** that subscribe to the special **input** channels; in subsequent steps, select the **actors** that subscribe to channels updated in the previous step.
* **Execution**: Execute all selected **actors** in parallel, until all complete, or one fails, or a timeout is reached. During this phase, channel updates are invisible to actors until the next step.
* **Update**: Update the channels with the values written by the **actors** in this step.

Repeat until no **actors** are selected for execution, or a maximum number of steps is reached.
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant correctly identifies LastValue as the default channel and explains that it overwrites earlier values, directly supported by excerpt [4].

## 7. q031 (multi; seed 21)

**Question:** Can I embed one compiled graph inside another graph, and where does the checkpointer go?

**Reference answer:** A compiled subgraph can be added as a node of the parent when it shares state keys. When schemas differ, call the subgraph's invoke inside a node function that maps parent state to subgraph state and back. Provide the checkpointer only when compiling the parent and it propagates to child subgraphs.

**must_mention:** checkpointer

**Answer:**

Yes, a compiled graph can be embedded inside another graph as a subgraph node. The parent graph can add the compiled subgraph directly with add_node when they share state keys [5][4]. The checkpointer is set on the parent graph’s compile call; the parent must be compiled with a checkpointer for subgraph persistence features like interrupts and durable execution to work [3]. The subgraph can inherit this checkpointer by omitting the checkpointer argument (default None) or you can choose a different mode, but compiling the subgraph with checkpointer=True and calling it multiple times can trigger the MULTIPLE_SUBGRAPHS error, so use the appropriate mode based on your needs [1].

**Excerpts (context order):**

[1] CITED MULTIPLE_SUBGRAPHS > Troubleshooting (https://docs.langchain.com/oss/python/langgraph/errors/MULTIPLE_SUBGRAPHS#troubleshooting)

```text
This error occurs when you call a subgraph inside a node multiple times, and the subgraph is compiled with `checkpointer=True` (continuations mode).

Choose one of the following based on your requirements:

1. **Don't need interrupts?** Use `checkpointer=False` to opt out of checkpointing entirely:
   ```python
   subgraph = subgraph_builder.compile(checkpointer=False)
   ```

2. **Need interrupts but not cross-invocation persistence?** Use the default inherited mode by omitting `checkpointer`:
   ```python
   subgraph = subgraph_builder.compile()
   ```
   Each invocation gets a unique namespace, so parallel execution works. The subgraph starts fresh each time but can use `interrupt()`.

3. **Need cross-invocation persistence?** Use `checkpointer=True`. LangGraph assigns each invocation a position-based namespace suffix (`calling_node`, `calling_node|1`, etc.) to prevent conflicts. For stable, name-based namespaces, wrap each subgraph with a unique node name — see parallel subgraphs.

- Subgraph persistence — full comparison of checkpointer modes
- Persistence — how checkpointers work in LangGraph
```

[2] NOT CITED Use the functional API > Calling graphs (https://docs.langchain.com/oss/python/langgraph/use-functional-api#calling-graphs)

```text
The **Functional API** and the **Graph API** can be used together in the same application as they share the same underlying runtime.

```python
from langgraph.func import entrypoint
from langgraph.graph import StateGraph

builder = StateGraph()
...
some_graph = builder.compile()

@entrypoint()
def some_workflow(some_input: dict) -> int:
    # Call a graph defined using the graph API
    result_1 = some_graph.invoke(...)
    # Call another graph defined using the graph API
    result_2 = another_graph.invoke(...)
    return {
        "result_1": result_1,
        "result_2": result_2
    }
```



  ```python
  from typing import TypedDict
  from langgraph.func import entrypoint
  from langgraph.checkpoint.memory import InMemorySaver
  from langgraph.graph import StateGraph

  # Define the shared state type
  class State(TypedDict):
      foo: int

  # Define a simple transformation node
  def double(state: State) -> State:
      return {"foo": state["foo"] * 2}

  # Build the graph using the Graph API
  builder = StateGraph(State)
  builder.add_node("double", double)
  builder.set_entry_point("double")
  graph = builder.compile()

  # Define the functional API workflow
  checkpointer = InMemorySaver()

  @entrypoint(checkpointer=checkpointer)
  def workflow(x: int) -> dict:
      result = graph.invoke({"foo": x})
      return {"bar": result["foo"]}

  # Execute the workflow
  config = {"configurable": {"thread_id": str(uuid7())}}
  print(workflow.invoke(5, config=config))  # Output: {'bar': 10}
  ```
```

[3] CITED Subgraphs > Subgraph persistence (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#subgraph-persistence)

```text
When you use a subgraph, you need to decide what happens to its internal data between calls. Consider a customer support bot that delegates to specialist subagents: should the "billing expert" subagent remember the customer's earlier questions, or start fresh each time it's called?

The `checkpointer` parameter on `.compile()` controls subgraph persistence:

| Mode | `checkpointer=` | Behavior |
|------|-----------------|----------|
| Per-invocation | `None` (default) | Each call starts fresh and inherits the parent's checkpointer to support interrupts and durable execution within a single call. |
| Per-thread | `True` | State accumulates across calls on the same thread. Each call picks up where the last one left off. |
| Stateless | `False` | No checkpointing at all—runs like a plain function call. No interrupts or durable execution. |

Per-invocation is the right choice for most applications, including multi-agent systems where subagents handle independent requests. Use per-thread when a subagent needs multi-turn conversation memory (for example, a research assistant that builds context over several exchanges).


The parent graph must be compiled with a checkpointer for subgraph persistence features (interrupts, state inspection, per-thread memory) to work. See persistence.



The examples below use LangChain's @`create_agent`], which is a common way to build agents. `create_agent` produces a [LangGraph graph under the hood, so all subgraph persistence concepts apply directly. If you're building with raw LangGraph `StateGraph`, the same patterns and configuration options apply—see the Graph API for details.
```

[4] CITED Subgraphs > Define subgraph communication (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#define-subgraph-communication)

```text
When adding subgraphs, you need to define how the parent graph and the subgraph communicate:

| Pattern | When to use | State schemas |
|---------|------------|--------------|
| Call a subgraph inside a node | Parent and subgraph have **different state schemas** (no shared keys), or you need to transform state between them | You write a wrapper function that maps parent state to subgraph input and subgraph output back to parent state |
| Add a subgraph as a node | Parent and subgraph **share state keys**—the subgraph reads from and writes to the same channels as the parent | You pass the compiled subgraph directly to `add_node`—no wrapper function needed |
```

[5] CITED Subgraphs (https://docs.langchain.com/oss/python/langgraph/use-subgraphs)

```text
This guide explains the mechanics of using subgraphs. A subgraph is a graph that is used as a node in another graph.

Subgraphs are useful for:
- Building multi-agent systems
- Reusing a set of nodes in multiple graphs
- Distributing development: when you want different teams to work on different parts of the graph independently, you can define each part as a subgraph, and as long as the subgraph interface (the input and output schemas) is respected, the parent graph can be built without knowing any details of the subgraph
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant correctly states that a compiled graph can be embedded as a subgraph, explains how to add it, and details how checkpointers work on the parent and subgraph based on the cited excerpts.

## 8. q033 (multi; seed 21)

**Question:** When an orchestrator dispatches sub-agents through tools, how do I print the parent agent's own tokens and also follow each sub-agent's messages from a single streaming run?

**Reference answer:** Call graph.stream_events(input, version="v3"). Iterate stream.messages and print the tokens of each message.text to stream the parent's output, and iterate stream.subgraphs to follow nested work: each subgraph exposes graph_name, path and its own messages, and a named agent dispatched from a tool appears under its name.

**must_mention:** stream_events, subgraphs

**Answer:**

Enable subgraph streaming on the orchestrator by calling `graph.stream(..., subgraphs=True, stream_mode="messages", version="v2")`. The stream yields chunks where `chunk["ns"]` is `()` for the root graph (the parent agent) and a tuple like `("agent:<task_id>",)` for each dispatched sub‑agent, so printing `chunk["data"]` shows the parent’s own token chunks together with the sub‑agents’ token chunks in a single run [1][3].

If you want to avoid parsing the namespace strings, use the event‑stream interface: `stream = graph.stream_events(input, version="v3")` and then iterate `for subgraph in stream.subgraphs:`. Each `subgraph` provides `subgraph.graph_name` (the sub‑agent’s name) and an iterable `subgraph.messages` that you can print, while the root stream still outputs the parent’s tokens [2].

```python
# Parent + sub‑agents in one stream
for chunk in graph.stream(
 {"messages": [{"role": "user", "content": "..."}]},
 stream_mode="messages",
 subgraphs=True,
 version="v2",
):
 print("source", chunk["ns"], "data", chunk["data"]) # parent or sub‑agent tokens

# Alternative: use subgraph iterator
stream = graph.stream_events({"messages": [{"role": "user", "content": "..."}]}, version="v3")
for sub in stream.subgraphs:
 print("Subgraph", sub.graph_name)
 for msg in sub.messages:
 print(msg.text)
```

**Excerpts (context order):**

[1] CITED Streaming > Stream modes > Subgraph outputs (https://docs.langchain.com/oss/python/langgraph/streaming#subgraph-outputs)

```text
```python
    from langchain.agents import create_agent
    from langgraph.graph import END, START, StateGraph

    graph = (
        StateGraph(State)
        .add_node("agent", create_agent(model, tools, state_schema=State))
        .add_edge(START, "agent")
        .add_edge("agent", END)
        .compile()
    )

    for chunk in graph.stream(
        {"messages": [{"role": "user", "content": "..."}]},
        stream_mode="messages",
        subgraphs=True,  # [!code highlight]
        version="v2",
    ):
        print(chunk["type"])  # "messages"
        print(chunk["ns"])    # () for root, ("agent:<task_id>",) for subgraph
        print(chunk["data"])  # (token, metadata)
    ```
```

[2] CITED Event streaming > Stream subgraphs (https://docs.langchain.com/oss/python/langgraph/event-streaming#stream-subgraphs)

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

[3] CITED Streaming > Stream modes > Subgraph outputs (https://docs.langchain.com/oss/python/langgraph/streaming#subgraph-outputs)

```text
To include outputs from subgraphs in the streamed outputs, you can set `subgraphs=True` in the `.stream()` method of the parent graph. This will stream outputs from both the parent graph and any subgraphs.

The outputs will be streamed as tuples `(namespace, data)`, where `namespace` is a tuple with the path to the node where a subgraph is invoked, e.g. `("parent_node:", "child_node:")`.

With `version="v2"`, subgraph events use the same `StreamPart` format. The `ns` field identifies the source:

```python
    for chunk in graph.stream(
        {"foo": "foo"},
        subgraphs=True,  # [!code highlight]
        stream_mode="updates",
        version="v2", # [!code highlight]
    ):
        print(chunk["type"])  # "updates"
        print(chunk["ns"])    # () for root, ("node_name:<task_id>",) for subgraph
        print(chunk["data"])  # {"node_name": {"key": "value"}}
    ```

```python
    for chunk in graph.stream(
        {"foo": "foo"},
        # Set subgraphs=True to stream outputs from subgraphs
        subgraphs=True,  # [!code highlight]
        stream_mode="updates",
    ):
        print(chunk)
    ```

This applies to every `stream_mode`, including `"messages"`. Agent builders like @[`create_agent`] return a **compiled graph**, so adding one as a node turns it into a subgraph. Without `subgraphs=True`, `stream_mode="messages"` on the parent graph will not emit token chunks from the inner agent's LLM calls. Invoking `agent.stream(...)` directly will, which is why this often shows up only after wrapping.
```

[4] NOT CITED Subgraphs > Subgraph persistence > Stateful (https://docs.langchain.com/oss/python/langgraph/use-subgraphs#stateful)

```text
```python
  from langgraph.graph import MessagesState, StateGraph

  def create_sub_agent(model, *, name, **kwargs):
      """Wrap an agent with a unique node name for namespace isolation."""
      agent = create_agent(model=model, name=name, **kwargs)
      return (
          StateGraph(MessagesState)
          .add_node(name, agent)  # unique name → stable namespace  # [!code highlight]
          .add_edge("__start__", name)
          .compile()
      )

  fruit_agent = create_sub_agent(
      "gpt-5.4-mini", name="fruit_agent",
      tools=[fruit_info], prompt="...", checkpointer=True,
  )
  veggie_agent = create_sub_agent(
      "gpt-5.4-mini", name="veggie_agent",
      tools=[veggie_info], prompt="...", checkpointer=True,
  )

  config = {"configurable": {"thread_id": "1"}}

  # First call - LLM calls both fruit and veggie experts
  response = agent.invoke(
      {"messages": [{"role": "user", "content": "Tell me about cherries and broccoli"}]},
      config=config,
  )
  # Fruit subagent message count: 4
  # Veggie subagent message count: 4

  # Second call - both agents accumulate independently
  response = agent.invoke(
      {"messages": [{"role": "user", "content": "Now tell me about oranges and carrots"}]},
      config=config,
  )
  # Fruit subagent message count: 8 (remembers cherries!)
  # Veggie subagent message count: 8 (remembers broccoli!)
  ```

Subgraphs added as nodes already get name-based namespaces automatically, so they don't need this wrapper.
```

[5] NOT CITED Workflows and agents (https://docs.langchain.com/oss/python/langgraph/workflows-agents)

```text
This guide reviews common workflow and agent patterns.

- Workflows have predetermined code paths and are designed to operate in a certain order.
- Agents are dynamic and define their own processes and tool usage.



LangGraph offers several benefits when building agents and workflows, including persistence, streaming, and support for debugging as well as deployment.


Trace and compare these workflow patterns with LangSmith. Follow the tracing quickstart to see how data flows through each step. We recommend you also set up LangSmith Engine which monitors your traces, detects issues, and proposes fixes.
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant provides correct methods using both graph.stream with subgraphs=True and stream_events with stream.subgraphs. All claims are fully backed by the cited excerpts.

## 9. q040 (version; seed 21)

**Question:** How can I configure graph-wide retry and error handler defaults across all nodes?

**Reference answer:** Call set_node_defaults on the StateGraph builder to set shared retry_policy, error_handler, timeout or cache_policy for all nodes; per-node values still take precedence.

**must_mention:** set_node_defaults

**Answer:**

Use the graph’s `set_node_defaults` method (available in `langgraph>=1.2`) to specify a `RetryPolicy` and an `error_handler` once for the entire graph. The defaults are applied to every node when the graph is compiled, and any per‑node values passed to `add_node` will override them. Example:
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
```[1][3]

**Excerpts (context order):**

[1] CITED Fault tolerance > Graph defaults (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#graph-defaults)

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

[2] NOT CITED Fault tolerance > Graph defaults > Applicability matrix (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#applicability-matrix)

```text
Not all defaults apply to all node types. Error-handler nodes (those registered via `add_node(error_handler=...)`) are excluded from certain defaults to prevent unsafe behavior:

| `set_node_defaults` parameter | Applies to regular nodes | Applies to error-handler nodes | Reason |
| ----------------------------- | ------------------------ | ------------------------------ | ------ |
| `retry_policy` | ✅ | ✅ | Handlers should be retried on transient failures |
| `timeout` | ✅ | ✅ | Stuck handlers should be cancelled like stuck regular nodes |
| `error_handler` | ✅ | ❌ | Handlers must never catch themselves |
| `cache_policy` | ✅ | ❌ | Caching handler results is unsafe |

Defaults set on a parent graph are **not** inherited by subgraphs. Each graph maintains its own defaults.
```

[3] CITED Use the graph API > Set graph-wide node defaults (https://docs.langchain.com/oss/python/langgraph/use-graph-api#set-graph-wide-node-defaults)

```text
Requires `langgraph>=1.2`.


Use @[`set_node_defaults`] to set `retry_policy`, `timeout`, `cache_policy`, or `error_handler` once for every node in a graph, instead of repeating them on each @[`add_node`] call. Per-node values always win, and defaults are applied at @[`StateGraph.compile`] time:

```python
from langgraph.types import RetryPolicy, TimeoutPolicy

graph = (
    StateGraph(State)
    .set_node_defaults(
        retry_policy=RetryPolicy(max_attempts=3),
        timeout=TimeoutPolicy(run_timeout=30),
        error_handler=fallback_handler,
    )
    .add_node("a", node_a)
    .add_node("b", node_b, retry_policy=RetryPolicy(max_attempts=5))  # overrides default
    .add_edge(START, "a")
    .compile()
)
```

`retry_policy` and `timeout` defaults apply to every node, including error-handler nodes. `cache_policy` and `error_handler` defaults apply only to regular nodes—handlers never catch themselves, and caching a handler result is unsafe. Defaults are not inherited by subgraphs.

See Fault tolerance for the full precedence rules and applicability table.
```

[4] NOT CITED Fault tolerance > Graph defaults > Default error handler (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#default-error-handler)

```text
The `error_handler` default is particularly valuable when every graph run maps to an external process (for example a background job row) and any unhandled node failure should mark that process as failed, without repeating `error_handler=` on every `add_node`. Per-node handlers still take precedence when a step needs its own logic:

```python
from langgraph.errors import NodeError
from langgraph.graph import StateGraph, START
from langgraph.types import Command, RetryPolicy
from typing_extensions import TypedDict

class State(TypedDict):
    process_id: str
    status: str

def fetch_data(state: State) -> State:
    return {"status": "fetched"}

def charge_payment(state: State) -> State:
    raise RuntimeError("payment timeout")

def finalize(state: State) -> State:
    return state

def mark_process_failed(state: State, error: NodeError) -> State:
    # Persist failure on the external process row keyed by process_id.
    return {"status": f"failed at {error.node}: {error.error}"}

def refund_payment(state: State, error: NodeError) -> Command:
    return Command(
        update={"status": f"compensated after {error.node}"},
        goto="finalize",
    )

graph = (
    StateGraph(State)
    .set_node_defaults(
        retry_policy=RetryPolicy(max_attempts=3),
        error_handler=mark_process_failed,
    )
    .add_node("fetch_data", fetch_data)  # uses mark_process_failed
    .add_node(
        "charge_payment",
        charge_payment,
        error_handler=refund_payment,  # overrides the graph-wide default
    )
    .add_node("finalize", finalize)
    .add_edge(START, "fetch_data")
    .add_edge("fetch_data", "charge_payment")
    .compile()
)
```
```

[5] NOT CITED Fault tolerance (https://docs.langchain.com/oss/python/langgraph/fault-tolerance)

```text
When a node fails—from a slow external API, a transient network error, or an unhandled exception—LangGraph gives you three composable mechanisms to respond:

- **Retries**: automatically re-run failed attempts based on exception type and backoff settings
- **Timeouts**: cap how long a single attempt may run
- **Error handling**: run a recovery function after all retries are exhausted

Use **`set_node_defaults`** to configure these mechanisms once for all nodes instead of repeating them on every `add_node` call.

These compose in a fixed order: when a node attempt raises any exception (including @[`NodeTimeoutError`] from a timeout), the retry policy decides whether to retry. Only after retries are exhausted does the error handler run.

For stopping a run cleanly at a superstep boundary and resuming later, see Graceful shutdown.

Per-node timeouts and node-level error handlers require `langgraph>=1.2`.
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant correctly explains using `set_node_defaults` on StateGraph to configure graph-wide retry and error handler defaults, matching the reference answer and supported by the cited excerpts.

## 10. q041 (version; seed 21)

**Question:** How do I attach a dedicated error handler to a node when all retries fail?

**Reference answer:** Pass error_handler=fn to add_node; fn takes the state and an injected error: NodeError parameter and can return a Command to update state and route elsewhere. It runs only after retries are exhausted.

**must_mention:** error_handler, NodeError

**Answer:**

Create a function that takes the current state and a `NodeError` and returns a `Command` describing how to recover. Then pass that function to the node via the `error_handler=` argument of `add_node` (or `builder.add_node`). The handler is invoked only after the node’s `retry_policy` has been exhausted, allowing you to update the state or jump to another node.

```python
from langgraph.errors import NodeError
from langgraph.types import Command, RetryPolicy

def payment_error_handler(state: State, error: NodeError) -> Command:
 return Command(
 update={"status": f"compensated: {error.error}"},
 goto="finalize",
 )

builder.add_node(
 "charge_payment",
 charge_payment,
 retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
 error_handler=payment_error_handler,
)
```

This registers a dedicated error handler for the `charge_payment` node that runs after all retries fail.[2][4]

**Excerpts (context order):**

[1] NOT CITED Fault tolerance > Graph defaults > Default error handler (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#default-error-handler)

```text
If `fetch_data` fails after retries, `mark_process_failed` runs. If `charge_payment` fails after retries, `refund_payment` runs instead because the per-node handler overrides the default.

The handler accepts the same `(state, error: NodeError)` signature described in Error handling. It also accepts `RunnableConfig` as an optional third argument if you need access to config values such as `thread_id`:

```python
from langchain_core.runnables import RunnableConfig

def mark_process_failed(
    state: State, error: NodeError, config: RunnableConfig
) -> State:
    thread_id = config["configurable"].get("thread_id")
    return {"status": f"failed on thread {thread_id}: {error.error}"}
```
```

[2] CITED Use the graph API > Handle node errors (https://docs.langchain.com/oss/python/langgraph/use-graph-api#handle-node-errors)

```text
The `error_handler=` parameter on @[`add_node`] registers a function that runs after a node fails and all retries are exhausted. The handler receives the current state and a typed @[`NodeError`] with failure context, and can route to a recovery branch via @[`Command`]:


Node-level error handlers require `langgraph>=1.2`.


```python
from langgraph.errors import NodeError
from langgraph.types import Command, RetryPolicy

def payment_error_handler(state: State, error: NodeError) -> Command:
    return Command(
        update={"status": f"compensated: {error.error}"},
        goto="finalize",
    )

builder.add_node(
    "charge_payment",
    charge_payment,
    retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
    error_handler=payment_error_handler,
)
```

See Fault tolerance for compensation patterns and `Command` routing.
```

[3] NOT CITED Thinking in LangGraph > Step 4: Build your nodes > Handle errors appropriately (https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately)

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

[4] CITED Fault tolerance > Error handling (https://docs.langchain.com/oss/python/langgraph/fault-tolerance#error-handling)

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

[5] NOT CITED Fault tolerance (https://docs.langchain.com/oss/python/langgraph/fault-tolerance)

```text
When a node fails—from a slow external API, a transient network error, or an unhandled exception—LangGraph gives you three composable mechanisms to respond:

- **Retries**: automatically re-run failed attempts based on exception type and backoff settings
- **Timeouts**: cap how long a single attempt may run
- **Error handling**: run a recovery function after all retries are exhausted

Use **`set_node_defaults`** to configure these mechanisms once for all nodes instead of repeating them on every `add_node` call.

These compose in a fixed order: when a node attempt raises any exception (including @[`NodeTimeoutError`] from a timeout), the retry policy decides whether to retry. Only after retries are exhausted does the error handler run.

For stopping a run cleanly at a superstep boundary and resuming later, see Graceful shutdown.

Per-node timeouts and node-level error handlers require `langgraph>=1.2`.
```

**Judge verdict:** correctness=2, citation_support=1

**Judge rationale:** The assistant correctly explained how to attach an error handler using the error_handler parameter in add_node, covering NodeError, Command, and retry policy exhaustion. All claims are fully supported by the cited excerpts.

## 11. q024 (single; added: judge score < 2)

**Question:** Why does parallel branching fail when two nodes write to the identical state attribute?

**Reference answer:** When several nodes in a fan-out return a value for the same key in one step and the key has no reducer, the graph raises a concurrent update error because it is uncertain how to merge them. Define the key with a reducer, e.g. Annotated[list, operator.add].

**must_mention:** operator.add

**Answer:**

Parallel branches run in the same superstep, and all updates are applied transactionally. If two nodes try to write to the same state attribute in that superstep, LangGraph cannot determine a consistent ordering for the writes, so it raises an error (e.g., InvalidUpdateError). This conflict causes the parallel branch to fail. To avoid the issue, write each node’s output to a separate field (or include an ordering value) so the updates can be merged deterministically.

**Excerpts (context order):**

[1] CITED Use the graph API > Create branches > Run graph nodes in parallel (https://docs.langchain.com/oss/python/langgraph/use-graph-api#run-graph-nodes-in-parallel)

```text
In the above example, nodes `"b"` and `"c"` are executed concurrently in the same superstep. Because they are in the same step, node `"d"` executes after both `"b"` and `"c"` are finished.

Importantly, updates from a parallel superstep may not be ordered consistently. If you need a consistent, predetermined ordering of updates from a parallel superstep, you should write the outputs to a separate field in the state together with a value with which to order them.

LangGraph executes nodes within supersteps, meaning that while parallel branches are executed in parallel, the entire superstep is **transactional**. If any of these branches raises an exception, **none** of the updates are applied to the state (the entire superstep errors).

Importantly, when using a checkpointer, results from successful nodes within a superstep are saved, and don't repeat when resumed.

If you have error-prone (perhaps want to handle flakey API calls), LangGraph provides two ways to address this:

1. You can write regular python code within your node to catch and handle exceptions.
  2. You can set a **`RetryPolicy`** to direct the graph to retry nodes that raise certain types of exceptions. Only failing branches are retried, so you needn't worry about performing redundant work.

Together, these let you perform parallel execution and fully control exception handling.

**Set max concurrency**
You can control the maximum number of concurrent tasks by setting `max_concurrency` in the configuration when invoking the graph. `max_concurrency` is a standalone config key, so set it at the top level of the config rather than inside `configurable`.

```python
graph.invoke({"value_1": "c"}, {"max_concurrency": 10})
```
```

[2] NOT CITED Workflows and agents > Parallelization (https://docs.langchain.com/oss/python/langgraph/workflows-agents#parallelization)

```text
```python Graph API
# Graph state
class State(TypedDict):
    topic: str
    joke: str
    story: str
    poem: str
    combined_output: str


# Nodes
def call_llm_1(state: State):
    """First LLM call to generate initial joke"""

    msg = llm.invoke(f"Write a joke about {state['topic']}")
    return {"joke": msg.content}


def call_llm_2(state: State):
    """Second LLM call to generate story"""

    msg = llm.invoke(f"Write a story about {state['topic']}")
    return {"story": msg.content}


def call_llm_3(state: State):
    """Third LLM call to generate poem"""

    msg = llm.invoke(f"Write a poem about {state['topic']}")
    return {"poem": msg.content}


def aggregator(state: State):
    """Combine the joke, story and poem into a single output"""

    combined = f"Here's a story, joke, and poem about {state['topic']}!\n\n"
    combined += f"STORY:\n{state['story']}\n\n"
    combined += f"JOKE:\n{state['joke']}\n\n"
    combined += f"POEM:\n{state['poem']}"
    return {"combined_output": combined}


# Build workflow
parallel_builder = StateGraph(State)

# Add nodes
parallel_builder.add_node("call_llm_1", call_llm_1)
parallel_builder.add_node("call_llm_2", call_llm_2)
parallel_builder.add_node("call_llm_3", call_llm_3)
parallel_builder.add_node("aggregator", aggregator)

# Add edges to connect nodes
parallel_builder.add_edge(START, "call_llm_1")
parallel_builder.add_edge(START, "call_llm_2")
parallel_builder.add_edge(START, "call_llm_3")
parallel_builder.add_edge("call_llm_1", "aggregator")
parallel_builder.add_edge("call_llm_2", "aggregator")
parallel_builder.add_edge("call_llm_3", "aggregator")
parallel_builder.add_edge("aggregator", END)
parallel_workflow = parallel_builder.compile()

# Show workflow
display(Image(parallel_workflow.get_graph().draw_mermaid_png()))

# Invoke
state = parallel_workflow.invoke({"topic": "cats"})
print(state["combined_output"])
```
```

[3] CITED Use time-travel > Fork > From a specific node (https://docs.langchain.com/oss/python/langgraph/use-time-travel#from-a-specific-node)

```text
When you call @`update_state`], values are applied using the specified node's writers (including [reducers). The checkpoint records that node as having produced the update, and execution resumes from that node's successors.

By default, LangGraph infers `as_node` from the checkpoint's version history. When forking from a specific checkpoint, this inference is almost always correct.

Specify `as_node` explicitly when:

- **Parallel branches**: Multiple nodes updated state in the same step, and LangGraph can't determine which was last (`InvalidUpdateError`).
- **No execution history**: Setting up state on a fresh thread (common in testing).
- **Skipping nodes**: Set `as_node` to a later node to make the graph think that node already ran.

```python
# graph: generate_topic -> write_joke

# Treat this update as if generate_topic produced it.
# Execution resumes at write_joke (the successor of generate_topic).
fork_config = graph.update_state(
    before_joke.config,
    values={"topic": "chickens"},
    as_node="generate_topic",
)
```
```

[4] NOT CITED Graph API overview > State > Schema (https://docs.langchain.com/oss/python/langgraph/graph-api#schema)

```text
There are two subtle and important points to note here:

1. We pass `state: InputState` as the input schema to `node_1`. But, we write out to `foo`, a channel in `OverallState`. How can we write out to a state channel that is not included in the input schema? This is because a node _can write to any state channel in the graph state._ The graph state is the union of the state channels defined at initialization, which includes `OverallState` and the filters `InputState` and `OutputState`.

2. We initialize the graph with:

```python
    StateGraph(
        OverallState,
        input_schema=InputState,
        output_schema=OutputState
    )
    ```

How can we write to `PrivateState` in `node_2`? How does the graph gain access to this schema if it was not passed in the `StateGraph` initialization?

We can do this because `_nodes` can also declare additional state `channels_` as long as the state schema definition exists. In this case, the `PrivateState` schema is defined, so we can add `bar` as a new state channel in the graph and write to it.

**Private channels are not redacted when streaming.**

Input, output, and private schemas constrain what each node _reads_ (its input schema) and what `invoke` _returns_ (the output schema). They do **not** hide channels from `stream`.

When you stream with `stream_mode="values"`, the graph emits **all** of its state channels by default, including private ones, because values streaming defaults to the full set of state channels rather than the output schema. This is why a private channel like `bar` is hidden by `invoke` but visible while streaming:

To restrict the streamed values to a specific set of channels (e.g. only the output schema), pass `output_keys`:
```

[5] NOT CITED Use the graph API > Create branches (https://docs.langchain.com/oss/python/langgraph/use-graph-api#create-branches)

```text
Parallel execution of nodes is essential to speed up overall graph operation. LangGraph offers native support for parallel execution of nodes, which can significantly enhance the performance of graph-based workflows. This parallelization is achieved through fan-out and fan-in mechanisms, utilizing both standard edges and @[conditional_edges][add_conditional_edges]. Below are some examples showing how to add create branching dataflows that work for you.
```

**Judge verdict:** correctness=1, citation_support=1

**Judge rationale:** The assistant correctly notes that parallel branches run in the same superstep and writes to the same attribute cause conflicts. However, it misses the core LangGraph concept mentioned in the reference answer: defining the state key with a reducer (like operator.add) to handle concurrent updates.
