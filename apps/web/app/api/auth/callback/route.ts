import { NextRequest, NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const error = request.nextUrl.searchParams.get("error");

  if (error || !code || !state) {
    return NextResponse.redirect(
      new URL("/?auth=failed", request.url),
    );
  }

  const upstream = await fetch(
    apiBaseUrl + "/api/v1/auth/oidc/callback",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(request.headers.get("cookie")
          ? { Cookie: request.headers.get("cookie")! }
          : {}),
      },
      body: JSON.stringify({ code, state }),
      cache: "no-store",
    },
  );

  if (!upstream.ok) {
    return NextResponse.redirect(
      new URL("/?auth=failed", request.url),
    );
  }

  const response = NextResponse.redirect(
    new URL("/", request.url),
  );
  response.cookies.delete(
    process.env.TITAN_OIDC_STATE_COOKIE_NAME ?? "titan_oidc_state",
  );
  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }
  return response;
}
