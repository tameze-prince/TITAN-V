import { NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET() {
  const upstream = await fetch(
    apiBaseUrl + "/api/v1/auth/oidc/start",
    {
      redirect: "manual",
      cache: "no-store",
    },
  );

  const location = upstream.headers.get("location");
  if (!location) {
    return new NextResponse("OIDC authentication is not configured", {
      status: upstream.status || 503,
      headers: { "Content-Type": "text/plain" },
    });
  }

  const response = NextResponse.redirect(location);
  const setCookie = upstream.headers.get("set-cookie");
  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }
  return response;
}
