import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const upstream = await fetch(
    apiBaseUrl + "/api/v1/auth/session",
    {
      headers: {
        Accept: "application/json",
        ...(request.headers.get("cookie")
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
