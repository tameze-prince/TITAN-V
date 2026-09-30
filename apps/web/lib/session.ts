import { cookies } from "next/headers";

const cookieName =
  process.env.TITAN_SESSION_COOKIE_NAME ?? "titan_session";

export async function browserSessionCookie(): Promise<string | null> {
  const store = await cookies();
  const value = store.get(cookieName)?.value;
  return value ? cookieName + "=" + value : null;
}

export { cookieName as TITAN_SESSION_COOKIE_NAME };
