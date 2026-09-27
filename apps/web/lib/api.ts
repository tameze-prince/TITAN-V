const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";

export async function titanFetch<T>(path: string): Promise<T> {
  const response = await fetch(apiBaseUrl + path, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("TITAN API returned " + response.status);
  }

  return (await response.json()) as T;
}
