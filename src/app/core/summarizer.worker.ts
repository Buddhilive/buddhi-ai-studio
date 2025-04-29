/// <reference lib="webworker" />

import { pipeline } from "@huggingface/transformers";

addEventListener('message', async ({ data }) => {
  const { content } = data;
  try {
    const summarizer = await pipeline('summarization', 'Xenova/distilbart-cnn-6-6');
    const summary = await summarizer(content);
    postMessage(summary);
  } catch (error) {
    console.log('Error in summarization:', error);
    postMessage({ error: 'Error in summarization' });
  }
});
