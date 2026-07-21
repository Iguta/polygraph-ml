import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("direct artifact uploads", () => {
  it("uses signed S3 headers without exposing the session token", async () => {
    sessionStorage.setItem("polygraphml.session", "secret-session-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.putUpload(
      "https://artifacts.example.test/signed",
      new File(["a,b\n1,2\n"], "evidence.csv", { type: "text/csv" }),
      {
        "Content-Type": "text/csv",
        "x-amz-meta-sha256": "abc123",
        "x-amz-server-side-encryption": "AES256",
      },
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(url).toBe("https://artifacts.example.test/signed");
    expect(headers.get("Authorization")).toBeNull();
    expect(headers.get("x-amz-meta-sha256")).toBe("abc123");
  });

  it("authenticates the local API upload fallback", async () => {
    sessionStorage.setItem("polygraphml.session", "local-session-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.putUpload(
      "/api/v1/projects/prj/artifacts/art/content",
      new File(["{}"], "model.json", { type: "application/json" }),
      { "Content-Type": "application/json" },
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(url).toBe("/api/v1/projects/prj/artifacts/art/content");
    expect(headers.get("Authorization")).toBe("Bearer local-session-token");
  });
});

describe("Decision Trace streaming", () => {
  it("authenticates SSE, resumes by event ID, and parses split frames", async () => {
    sessionStorage.setItem("polygraphml.session", "stream-session-token");
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'id: evt_2\nevent: evidence\ndata: {"event_id":"evt_2","audit_id":"aud_1","sequence":2,',
          ),
        );
        controller.enqueue(
          encoder.encode(
            '"type":"evidence","actor":"tool","created_at":"2026-07-20T00:00:00Z","payload":{"observation":"computed"},"provenance_refs":[]}\n\n',
          ),
        );
        controller.close();
      },
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(body, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const received: string[] = [];

    await api.streamEvents(
      "aud_1",
      1,
      "evt_1",
      (event) => received.push(event.event_id),
      new AbortController().signal,
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(url).toContain("after_sequence=1");
    expect(headers.get("Authorization")).toBe("Bearer stream-session-token");
    expect(headers.get("Last-Event-ID")).toBe("evt_1");
    expect(received).toEqual(["evt_2"]);
  });
});
