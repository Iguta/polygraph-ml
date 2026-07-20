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
