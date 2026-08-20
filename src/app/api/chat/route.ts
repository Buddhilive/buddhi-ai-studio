import { streamText, UIMessage, convertToModelMessages, createUIMessageStreamResponse, toUIMessageStream } from "ai";
import { createOpenAI } from '@ai-sdk/openai';

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

export async function POST(req: Request) {
    const {
        messages,
        model,
        webSearch,
    }: {
        messages: UIMessage[];
        model: string;
        webSearch: boolean;
    } = await req.json();

    // Only Gemma 4 E4B is served by the backend today
    const backendModelIds: Record<string, string> = { "gemma4-e4b": "gemma-4-e4b" };
    const validModels = Object.keys(backendModelIds);
    const selectedModel = validModels.includes(model) ? model : "gemma4-e4b";

    // TODO: wire up webSearch
    // if (webSearch) { ... }

    const backendUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
    const buddhiAIModel = createOpenAI({
        baseURL: `${backendUrl}/v1/`,
        apiKey: "",
    }).chat(backendModelIds[selectedModel]);

    const result = streamText({
        model: buddhiAIModel,
        messages: await convertToModelMessages(messages),
        system:
            "You are a helpful assistant that can answer questions and help with tasks",
    });

    // send sources and reasoning back to the client
    return createUIMessageStreamResponse({
        stream: toUIMessageStream({
            stream: result.stream,
            sendSources: true,
            sendReasoning: true,
        }),
    });
}