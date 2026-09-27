import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";
const operatorToken = process.env.TITAN_OPERATOR_API_TOKEN;

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string; workflowId: string }> },
) {
  const { projectId, workflowId } = await context.params;
  const body = await request.text();

  const upstream = await fetch(
    apiBaseUrl +
      "/api/v1/projects/" +
      projectId +
      "/workflows/" +
      workflowId +
      "/recovery/decision",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(operatorToken
          ? { Authorization: "Bearer " + operatorToken }
          : {}),
      },
      body,
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
