import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";
const operatorToken = process.env.TITAN_OPERATOR_API_TOKEN;

export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  context: {
    params: Promise<{ projectId: string; taskId: string }>;
  },
) {
  const { projectId, taskId } = await context.params;

  const upstream = await fetch(
    apiBaseUrl +
      "/api/v1/projects/" +
      projectId +
      "/tasks/" +
      taskId +
      "/approval",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(operatorToken
          ? { Authorization: "Bearer " + operatorToken }
          : request.headers.get("cookie")
            ? { Cookie: request.headers.get("cookie")! }
            : {}),
      },
      body: await request.text(),
      cache: "no-store",
    },
  );

  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
    },
  });
}
