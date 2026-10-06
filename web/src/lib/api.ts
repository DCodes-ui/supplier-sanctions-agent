export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/backend${path}`, init);
  } catch {
    throw new ApiError(0, "Could not reach the screening service.");
  }
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      message = response.statusText;
    }
    throw new ApiError(response.status, message);
  }
  const type = response.headers.get("content-type") ?? "";
  if (type.includes("text/csv")) return (await response.text()) as T;
  return response.json() as Promise<T>;
}
