const api = process.env.SCREENER_API_URL ?? "http://127.0.0.1:8000";

const offline = Response.json(
  {
    detail:
      "The screening service is not running. From the project folder, run: ./screener/.venv/bin/python -m screener api",
  },
  { status: 503 },
);

async function proxy(request: Request, path: string[]) {
  const url = new URL(request.url);
  const target = `${api}/${path.join("/")}${url.search}`;
  try {
    const response = await fetch(target, {
      method: request.method,
      headers: request.headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
    });
    return new Response(response.body, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return offline;
  }
}

export function GET(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return context.params.then(({ path }) => proxy(request, path));
}

export function POST(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return context.params.then(({ path }) => proxy(request, path));
}
