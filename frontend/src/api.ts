import type { Run, RunCreate, ModelInfo, ProviderInfo } from './types';

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const error = await response.json();
      if (error?.detail) {
        message = Array.isArray(error.detail)
          ? error.detail.map((d: any) => d.msg || d).join(', ')
          : error.detail;
      }
    } catch {
      try {
        const text = await response.text();
        if (text) message = `${message}: ${text.slice(0, 400)}`;
      } catch {
        /* swallow */
      }
    }
    throw new Error(message);
  }

  return response.json();
}

export async function getProviders(): Promise<ProviderInfo[]> {
  return fetchJson<ProviderInfo[]>(`${API_BASE}/providers`);
}

export async function getModels(): Promise<ModelInfo[]> {
  return fetchJson<ModelInfo[]>(`${API_BASE}/models`);
}

export async function createRun(data: RunCreate): Promise<Run> {
  return fetchJson<Run>(`${API_BASE}/runs`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function generateAnswers(runId: number): Promise<Run> {
  return fetchJson<Run>(`${API_BASE}/runs/${runId}/answers`, {
    method: 'POST',
  });
}

export async function evaluateRun(runId: number): Promise<Run> {
  return fetchJson<Run>(`${API_BASE}/runs/${runId}/evaluate`, {
    method: 'POST',
  });
}

export async function getRun(runId: number): Promise<Run> {
  return fetchJson<Run>(`${API_BASE}/runs/${runId}`);
}

export async function listRuns(): Promise<Run[]> {
  return fetchJson<Run[]>(`${API_BASE}/runs`);
}

export async function deleteRun(runId: number): Promise<void> {
  await fetchJson(`${API_BASE}/runs/${runId}`, {
    method: 'DELETE',
  });
}
