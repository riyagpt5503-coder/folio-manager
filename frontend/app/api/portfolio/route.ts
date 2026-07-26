import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.PYTHON_BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_request", message: "Request body must be valid JSON." },
      { status: 400 }
    );
  }

  try {
    const backendResponse = await fetch(`${BACKEND_URL}/api/portfolio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok && Array.isArray(data?.detail)) {
      const message = data.detail
        .map((d: { loc?: unknown[]; msg?: string }) => d.msg)
        .filter(Boolean)
        .join("; ");
      return NextResponse.json(
        { error: "invalid_request", message: message || "Invalid request." },
        { status: backendResponse.status }
      );
    }

    return NextResponse.json(data, { status: backendResponse.status });
  } catch {
    return NextResponse.json(
      {
        error: "backend_unreachable",
        message: "Could not reach the portfolio backend. Is it running on " + BACKEND_URL + "?",
      },
      { status: 502 }
    );
  }
}
