const API_ORIGIN = import.meta.env.VITE_API_URL ?? "";

export function apiUrl(path: string): string {
  return `${API_ORIGIN}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail?.detail ?? body.detail ?? message;
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return response.json() as Promise<T>;
}

export type UploadedAsset = {
  id: string;
  preview_url: string;
  width: number;
  height: number;
  sha256: string;
};

export type Frame = { index: number; url: string };
export type Generation = {
  id: string;
  status: "queued" | "running" | "ready" | "failed" | "cancelled";
  stage: string;
  completed: number;
  total: number;
  created_at?: string;
  frames: Frame[];
  frame_models: string[];
  warnings: string[];
  error?: { code: string; detail: string } | null;
  start_asset_id?: string;
  end_asset_id?: string;
};

export type EndpointInput = { asset: UploadedAsset };

export async function uploadAsset(file: File): Promise<UploadedAsset> {
  const form = new FormData();
  form.append("file", file);
  return request("/api/v1/assets", { method: "POST", body: form });
}

export function createGeneration(start: EndpointInput, end: EndpointInput, count: number) {
  return regenerateGeneration(start.asset.id, end.asset.id, count);
}

export function regenerateGeneration(startAssetId: string, endAssetId: string, count: number) {
  return request<Generation>("/api/v1/generations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify({
      start_asset_id: startAssetId,
      end_asset_id: endAssetId,
      inbetween_count: count,
    }),
  });
}

export function insertFrame(generationId: string, leftIndex: number, rightIndex: number) {
  return request<Frame>(`/api/v1/generations/${generationId}/frames/insert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ left_index: leftIndex, right_index: rightIndex }),
  });
}

export function getGeneration(id: string) {
  return request<Generation>(`/api/v1/generations/${id}`);
}

export async function listGenerations(cursor?: string) {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return request<{ items: Generation[]; next_cursor: string | null }>(`/api/v1/generations${query}`);
}

export function cancelGeneration(id: string) {
  return request<Generation>(`/api/v1/generations/${id}/cancel`, { method: "POST" });
}

export function deleteGeneration(id: string) {
  return request<{ deleted: boolean }>(`/api/v1/generations/${id}`, { method: "DELETE" });
}

export function createExport(
  id: string,
  settings: {
    format: "gif" | "png_zip";
    width: number;
    height: number;
    fps: number;
    ink_color: string;
    background_color: string;
    cutoff: number | null;
    cutoff_mode?: "raw" | "threshold" | "crisp";
    frame_indices?: number[];
    frame_styles?: Record<
      number,
      {
        ink_color: string;
        background_color: string;
        cutoff: number | null;
        cutoff_mode?: "raw" | "threshold" | "crisp";
      }
    >;
  },
) {
  return request<{ id: string; status: string; download_url: string }>(
    `/api/v1/generations/${id}/exports`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    },
  );
}
