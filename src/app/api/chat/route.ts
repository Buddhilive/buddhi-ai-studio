import { streamText, UIMessage, convertToModelMessages, createUIMessageStreamResponse, toUIMessageStream, wrapLanguageModel, extractReasoningMiddleware } from "ai";
import { createOpenAI } from '@ai-sdk/openai';

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

export async function POST(req: Request) {
    const {
        messages,
        model,
        enableThinking,
    }: {
        messages: UIMessage[];
        model: string;
        enableThinking?: boolean;
    } = await req.json();

    // Only Gemma 4 E4B is served by the backend today
    const backendModelIds: Record<string, string> = { "gemma4-e4b": "gemma-4-e4b" };
    const validModels = Object.keys(backendModelIds);
    const selectedModel = validModels.includes(model) ? model : "gemma4-e4b";

    const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
    const buddhiAIModel = wrapLanguageModel({
        model: createOpenAI({
            baseURL: `${backendUrl}/v1/`,
            apiKey: "",
            // The backend accepts a custom `enable_thinking` field; the OpenAI
            // client has no first-class option for it, so inject it here.
            fetch: async (input, init) => {
                if (init?.body && typeof init.body === "string") {
                    const body = JSON.parse(init.body);
                    body.enable_thinking = Boolean(enableThinking);
                    init = { ...init, body: JSON.stringify(body) };
                }
                return fetch(input, init);
            },
        }).chat(backendModelIds[selectedModel]),
        // The backend has no reasoning field the OpenAI Chat Completions
        // client understands, so it wraps reasoning in <think> tags inline
        // in the text stream; this splits it back into a reasoning part.
        middleware: extractReasoningMiddleware({ tagName: "think" }),
    });

    const result = streamText({
        model: buddhiAIModel,
        messages: await convertToModelMessages(messages),
        system:
            "You are a helpful assistant that can answer questions and help with tasks",
    });

    // send reasoning back to the client
    return createUIMessageStreamResponse({
        stream: toUIMessageStream({
            stream: result.stream,
            sendReasoning: true,
        }),
    });
}