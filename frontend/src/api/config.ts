const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined;

/** Empty string uses the Vite proxy (`/api` → FastAPI) during local development. */
export const API_BASE_URL = (explicit ?? "").replace(/\/$/, "");

export function apiUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const fromDetail =
      typeof body?.detail === "string"
        ? body.detail
        : body?.detail?.message || body?.detail?.error;
    const message = fromDetail || body?.message;
    const code = body?.detail?.code || body?.code;
    if (message) return code ? `${code}: ${message}` : String(message);
  } catch {
    /* ignore */
  }
  return `Request failed (${response.status})`;
}
