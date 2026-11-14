import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  convertToModelMessages,
  type UIMessage,
} from "ai";
import { nanoid } from "nanoid";

export const maxDuration = 120;

export async function POST(req: Request) {
  const {
    messages,
    model,
    enableThinking = true,
    egmMode = false,
    harnessCalibrate = false,
  }: {
    messages: UIMessage[];
    model: string;
    enableThinking?: boolean;
    egmMode?: boolean;
    harnessCalibrate?: boolean;
  } = await req.json();

  const selectedModel = model || "gemma-4-e4b";
  const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";

  const modelMessages = await convertToModelMessages(messages);

  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      const textId = nanoid();
      const reasoningId = nanoid();
      let hasStartedText = false;
      let hasStartedReasoning = false;

      try {
        const response = await fetch(`${backendUrl}/v1/agent/runs`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            messages: modelMessages,
            model: selectedModel,
            enable_thinking: Boolean(enableThinking),
            egm_mode: Boolean(egmMode),
            ...(harnessCalibrate ? { harness_mode: "calibrate" } : {}),
          }),
        });

        if (!response.ok || !response.body) {
          const errText = await response.text();
          writer.write({
            type: "text-start",
            id: textId,
          });
          writer.write({
            type: "text-delta",
            id: textId,
            delta: `Agent Error (${response.status}): ${errText}`,
          });
          writer.write({
            type: "text-end",
            id: textId,
          });
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith("data:")) continue;

            const jsonStr = trimmed.slice(5).trim();
            if (jsonStr === "[DONE]") {
              break;
            }

            try {
              const event = JSON.parse(jsonStr);

              // Forward lossless AgentEvent for the live Trajectory Event Stream
              writer.write({
                type: "data-trajectory",
                data: event,
              } as unknown as Parameters<typeof writer.write>[0]);

              switch (event.event) {
                case "reasoning.delta": {
                  if (!hasStartedReasoning) {
                    writer.write({
                      type: "reasoning-start",
                      id: reasoningId,
                    });
                    hasStartedReasoning = true;
                  }
                  writer.write({
                    type: "reasoning-delta",
                    id: reasoningId,
                    delta: event.data.delta,
                  });
                  break;
                }

                case "text.delta": {
                  if (!hasStartedText) {
                    writer.write({
                      type: "text-start",
                      id: textId,
                    });
                    hasStartedText = true;
                  }
                  writer.write({
                    type: "text-delta",
                    id: textId,
                    delta: event.data.delta,
                  });
                  break;
                }

                case "tool.call": {
                  writer.write({
                    type: "tool-call",
                    toolCallId: event.data.tool_call_id,
                    toolName: event.data.tool_name,
                    input: typeof event.data.arguments === "string"
                      ? JSON.parse(event.data.arguments || "{}")
                      : event.data.arguments,
                  } as unknown as Parameters<typeof writer.write>[0]);
                  break;
                }

                case "tool.result": {
                  writer.write({
                    type: "tool-result",
                    toolCallId: event.data.tool_call_id,
                    toolName: event.data.tool_name,
                    output: event.data.output,
                  } as unknown as Parameters<typeof writer.write>[0]);
                  break;
                }

                case "plan.update": {
                  writer.write({
                    type: "data-plan",
                    data: event.data.plan,
                  } as unknown as Parameters<typeof writer.write>[0]);
                  break;
                }

                case "node.start":
                case "node.end": {
                  writer.write({
                    type: "data-node",
                    data: { node: event.node, event: event.event },
                  } as unknown as Parameters<typeof writer.write>[0]);
                  break;
                }

                case "egm.phase":
                case "egm.reviewer.status":
                case "egm.artifact": {
                  writer.write({
                    type: "data-egm-status",
                    data: { event: event.event, ...event.data },
                  } as unknown as Parameters<typeof writer.write>[0]);
                  break;
                }

                case "egm.gate.pause": {
                  writer.write({
                    type: "data-egm-review",
                    data: { ...event.data, run_id: event.run_id },
                  } as unknown as Parameters<typeof writer.write>[0]);
                  break;
                }

                case "harness.propose":
                case "harness.probe":
                case "harness.compose":
                case "harness.distill": {
                  writer.write({
                    type: "data-harness-status",
                    data: { event: event.event, ...event.data },
                  } as unknown as Parameters<typeof writer.write>[0]);
                  break;
                }

                case "error": {
                  if (!hasStartedText) {
                    writer.write({ type: "text-start", id: textId });
                    hasStartedText = true;
                  }
                  writer.write({
                    type: "text-delta",
                    id: textId,
                    delta: `\n\n**Error**: ${event.data?.message || "Execution error"}\n`,
                  });
                  break;
                }

                default:
                  break;
              }
            } catch {
              // Ignore malformed JSON chunks
            }
          }
        }
      } catch (err: unknown) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        if (!hasStartedText) {
          writer.write({ type: "text-start", id: textId });
          hasStartedText = true;
        }
        writer.write({
          type: "text-delta",
          id: textId,
          delta: `\n\nConnection error: ${errorMsg}`,
        });
      } finally {
        if (hasStartedReasoning) {
          writer.write({ type: "reasoning-end", id: reasoningId });
        }
        if (hasStartedText) {
          writer.write({ type: "text-end", id: textId });
        }
      }
    },
  });

  return createUIMessageStreamResponse({ stream });
}
