const apiBaseUrl = process.env.TITAN_API_URL ?? "http://localhost:8000";

export async function titanFetch<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  const operatorToken = process.env.TITAN_OPERATOR_API_TOKEN;
  if (operatorToken) {
    headers.Authorization = "Bearer " + operatorToken;
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
