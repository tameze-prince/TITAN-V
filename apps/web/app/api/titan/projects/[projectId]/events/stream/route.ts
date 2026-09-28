import { NextRequest } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";
const operatorToken = process.env.TITAN_OPERATOR_API_TOKEN;

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const cursor =
    request.headers.get("last-event-id") ??
    request.nextUrl.searchParams.get("cursor");

  const upstream = await fetch(
    apiBaseUrl +
      "/api/v1/control-plane/projects/" +
      projectId +
      "/events/stream" +
      (cursor ? "?cursor=" + encodeURIComponent(cursor) : ""),
    {
      headers: {
        Accept: "text/event-stream",
        ...(operatorToken
          ? { Authorization: "Bearer " + operatorToken }
          : {}),
      },
      cache: "no-store",
    },
  );

  if (!upstream.body) {
    return new Response("TITAN event stream unavailable", {
      status: upstream.status || 503,
    });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Cache-Control": "no-cache, no-transform",
      "Content-Type": "text/event-stream",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
