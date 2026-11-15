import { createOpenAICompatible } from "@ai-sdk/openai-compatible";

const localLlmBaseUrl = process.env.LOCAL_LLM_BASE_URL ?? "http://backend:8000/v1";

export const localProvider = createOpenAICompatible({
  name: "buddhi-local",
  baseURL: localLlmBaseUrl,
  apiKey: process.env.LOCAL_LLM_API_KEY ?? "local-dev",
});

export function getDefaultModel() {
  const modelId = process.env.LOCAL_LLM_MODEL ?? "gemma-4-e4b";
  return localProvider(modelId);
}
