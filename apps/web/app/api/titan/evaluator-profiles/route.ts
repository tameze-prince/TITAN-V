import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";
const operatorToken = process.env.TITAN_OPERATOR_API_TOKEN;

export const dynamic = "force-dynamic";

function headers(request: NextRequest) {
  return {
    "Content-Type": "application/json",
    ...(operatorToken
      ? { Authorization: "Bearer " + operatorToken }
      : request.headers.get("cookie")
        ? { Cookie: request.headers.get("cookie")! }
        : {}),
  };
}

export async function GET(request: NextRequest) {
  const upstream = await fetch(
    apiBaseUrl + "/api/v1/control-plane/evaluator-profiles" + request.nextUrl.search,
    { headers: headers(request), cache: "no-store" },
  );

  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
    },
  });
}

export async function POST(request: NextRequest) {
  const upstream = await fetch(
    apiBaseUrl + "/api/v1/control-plane/evaluator-profiles",
    {
      method: "POST",
      headers: headers(request),
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
