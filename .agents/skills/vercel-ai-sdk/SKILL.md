---
name: vercel-ai-sdk
description: Official Vercel AI SDK v7 runbook for streamText, generateText, Output.object, useChat, @ai-sdk/mcp, and local Buddhi LLM integration.
version: 1.0.0
---

# Vercel AI SDK Runbook

- **Local-First Provider (`src/lib/ai.ts`)**: Always default to `createOpenAICompatible({ name: "buddhi-local", baseURL: process.env.LOCAL_LLM_BASE_URL ?? "http://backend:8000/v1" })` so generated AI apps run 100% self-hosted without external API keys.
- **Streaming Route (`src/app/api/chat/route.ts`)**: Use `streamText({ model: getDefaultModel(), messages: await convertToModelMessages(messages), tools })` and return `result.toUIMessageStreamResponse()`.
- **Structured Output**: Use `generateText({ model, output: Output.object({ schema: z.object(...) }), prompt })` with `zod`.
- **Client Chat Hook**: In `"use client"` components, use `useChat()` from `@ai-sdk/react` (`messages`, `sendMessage`, `status`, `stop`). Render chat logs with `role="log"` and `aria-busy={status === "streaming"}` (never place streaming tokens directly inside `aria-live="polite"`).
- **MCP Integration**: Use `createMCPClient` from `@ai-sdk/mcp` when connecting runtime AI tools to external or local MCP endpoints.
