import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";
const operatorToken = process.env.TITAN_OPERATOR_API_TOKEN;

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ profileId: string }> },
) {
  const { profileId } = await context.params;
  const upstream = await fetch(
    apiBaseUrl +
      "/api/v1/control-plane/evaluator-profiles/" +
      profileId +
      "/activate",
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
