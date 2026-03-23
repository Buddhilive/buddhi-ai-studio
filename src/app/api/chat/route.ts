import { streamText, UIMessage, convertToModelMessages } from "ai";
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

    const openai = createOpenAI({
        baseURL: 'http://localhost:8484/v1',
        apiKey: 'buddhi-ai',
        name: 'buddhi-ai',
    });

    const result = streamText({
        model: openai.chat('qwen3.5:2b'),
        messages: await convertToModelMessages(messages),
        system:
            "You are a helpful assistant that can answer questions and help with tasks",
    });

    // send sources and reasoning back to the client
    return result.toUIMessageStreamResponse({
        sendSources: true,
        sendReasoning: true,
    });
}