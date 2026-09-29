import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const upstream = await fetch(
    apiBaseUrl + "/api/v1/auth/logout",
    {
      method: "POST",
      headers: {
        ...(request.headers.get("cookie")
          ? { Cookie: request.headers.get("cookie")! }
          : {}),
      },
      cache: "no-store",
    },
  );

  const response = NextResponse.json(
    { authenticated: false },
    { status: upstream.ok ? 200 : upstream.status },
  );
  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }
  return response;
}
