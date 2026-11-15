import { convertToModelMessages, streamText, type UIMessage } from "ai";
import { getDefaultModel } from "@/lib/ai";

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json();

  const result = streamText({
    model: getDefaultModel(),
    messages: await convertToModelMessages(messages),
  });

  return result.toUIMessageStreamResponse();
}
