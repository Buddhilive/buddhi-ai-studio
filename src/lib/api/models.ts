export interface ModelDownloadRequest {
  model_id: string;
  quantization: string;
}

export interface ModelInfo {
  id: string;
  model_id?: string;
  name: string;
  quantization: string;
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'cancelled';
  progress?: number;
  total_size?: number;
  downloaded_size?: number;
  error?: string;
}

const API_BASE_URL = 'http://localhost:8484/api/v1';

export const modelsApi = {
  /**
   * List all models
   */
  async listModels(): Promise<ModelInfo[]> {
    const res = await fetch(`${API_BASE_URL}/models`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store'
    });
    if (!res.ok) {
      throw new Error(`Failed to list models: ${res.statusText}`);
    }
    return res.json();
  },

  /**
   * Start a model download
   */
  async downloadModel(data: ModelDownloadRequest): Promise<ModelInfo> {
    const res = await fetch(`${API_BASE_URL}/models/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => null);
      throw new Error(errorData?.detail || `Download failed: ${res.statusText}`);
    }
    return res.json();
  },

  /**
   * Check download status by ID
   */
  async getModelStatus(id: string): Promise<ModelInfo> {
    const res = await fetch(`${API_BASE_URL}/models/${id}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store'
    });
    if (!res.ok) {
      throw new Error(`Failed to get status for model ${id}`);
    }
    return res.json();
  },

  /**
   * Delete a model record and its files, or cancel download
   */
  async deleteModel(id: string): Promise<void> {
    const maxRetries = 2;
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const res = await fetch(`${API_BASE_URL}/models/${id}`, {
          method: 'DELETE',
        });

        let data = null;
        try {
            data = await res.json();
        } catch (e) {}

        if (!res.ok) {
            // Already deleted (404) — treat as success
            if (res.status === 404) {
                return;
            }
            // If the backend returns the model object but with a weird status code, treat it as success.
            if (data && data.id) {
                return;
            }
            throw new Error(data?.detail || data?.error_msg || `Failed to delete model: ${res.statusText}`);
        }
        return; // Success
      } catch (err: any) {
        lastError = err;
        // Retry on network errors, but not on API errors
        if (!(err instanceof TypeError && err.message.includes('Failed to fetch'))) {
          throw err; // Not a network error, throw immediately
        }
        if (attempt < maxRetries) {
          // Wait a bit before retrying (exponential backoff)
          await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 100));
        }
      }
    }

    // All retries exhausted
    throw lastError || new Error('Failed to delete model');
  },

  /**
   * Build the SSE URL for progress tracking
   */
  getProgressUrl(id: string): string {
    return `${API_BASE_URL}/models/${id}/progress`;
  }
};
