import type { ApiErrorBody, PortfolioRequestBody, PortfolioResponse } from "@/types/portfolio";

export class PortfolioApiError extends Error {
  constructor(public body: ApiErrorBody) {
    super(body.message);
  }
}

export async function fetchPortfolio(req: PortfolioRequestBody): Promise<PortfolioResponse> {
  const res = await fetch("/api/portfolio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new PortfolioApiError(data as ApiErrorBody);
  }

  return data as PortfolioResponse;
}
