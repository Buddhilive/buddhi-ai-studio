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

    // Validate model (fallback to gemma4-e2b if not recognized)
    const validModels = ["gemma4-e2b", "gemma4-e4b"];
    const selectedModel = validModels.includes(model) ? model : "gemma4-e2b";

    // TODO: wire up webSearch
    // if (webSearch) { ... }

    const buddhiAIModel = createOpenAI({
        baseURL: "http://localhost:9379/v1/",
        apiKey: "",
    }).chat(selectedModel);

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