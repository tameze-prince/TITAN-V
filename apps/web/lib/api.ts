import { cookies } from "next/headers";

const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";
const sessionCookieName =
  process.env.TITAN_SESSION_COOKIE_NAME ?? "titan_session";

export async function titanFetch<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  const operatorToken = process.env.TITAN_OPERATOR_API_TOKEN;
  if (operatorToken) {
    headers.Authorization = "Bearer " + operatorToken;
  } else {
    const store = await cookies();
    const session = store.get(sessionCookieName)?.value;
    if (session) {
      headers.Cookie = sessionCookieName + "=" + session;
    }
  }

  const response = await fetch(apiBaseUrl + path, {
    cache: "no-store",
    headers,
  });

  if (!response.ok) {
    throw new Error("TITAN API returned " + response.status);
  }

  return (await response.json()) as T;
}
