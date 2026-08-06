---
name: Adapter Proposal
about: Propose a new framework adapter
labels: ["adapter"]
---

## Framework Name and URL

<!-- e.g. AutoGen — https://github.com/microsoft/autogen -->

## Why This Framework?

What makes this framework worth instrumenting? Consider adoption, use cases,
and the kinds of agent workflows it enables.

## Trace Shape Considerations

How do agent executions look in this framework? Think about:

- What are the key operations (tool calls, sub-agent dispatch, policy
  evaluation, state transitions)?
- What metadata is available at each step?
- Are there error modes or recursive patterns worth detecting?

## Implementation Approach

A sketch of how you would instrument this framework:

- Which OpenTelemetry spans would you create, and where?
- What existing patterns in our codebase (e.g. the LangGraph adapter) apply?
- Are there any blocking questions or risks?

## Willing to Contribute?

<!-- Let us know if you plan to implement this yourself or are looking for a
maintainer to pick it up. -->
