import { NextResponse } from "next/server";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.redirect(
    apiBaseUrl + "/api/v1/auth/oidc/start",
  );
}
