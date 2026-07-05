import { describe, it, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const store: Record<string, string> = {};
const mockLocalStorage = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => { store[key] = value; },
  removeItem: (key: string) => { delete store[key]; },
  clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
  get length() { return Object.keys(store).length; },
  key: (i: number) => Object.keys(store)[i] ?? null,
};
Object.defineProperty(globalThis, "localStorage", { value: mockLocalStorage });

beforeEach(() => {
  mockFetch.mockReset();
  mockLocalStorage.clear();
});

async function loadApi() {
  return import("../api-client").then((m) => m.api);
}

describe("api-client", () => {
  it("leaderboard calls /api/v1/leaderboard", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: [], limit: 100, offset: 0 }),
    });
    const api = await loadApi();
    await api.leaderboard(100, 0);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/leaderboard?limit=100&offset=0",
      expect.objectContaining({ headers: expect.objectContaining({ "Content-Type": "application/json" }) }),
    );
  });

  it("leaderboardEdge calls /api/v1/leaderboard/edge", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: [], limit: 50, offset: 0 }),
    });
    const api = await loadApi();
    await api.leaderboardEdge(50, 0);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/leaderboard/edge?limit=50&offset=0",
      expect.anything(),
    );
  });

  it("marketDetail calls /api/v1/markets/{id}", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ id: "0x123", question: "Test?" }),
    });
    const api = await loadApi();
    const result = await api.marketDetail("0x123");
    expect(result.question).toBe("Test?");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/markets/0x123",
      expect.anything(),
    );
  });

  it("followWallet sends POST with body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ id: "abc", wallet: "0xabc" }),
    });
    const api = await loadApi();
    await api.followWallet("0xabc", { label: "test" });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/follow/0xabc",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ label: "test" }),
      }),
    );
  });

  it("unfollowWallet sends DELETE", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve() });
    const api = await loadApi();
    await api.unfollowWallet("0xabc");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/follow/0xabc",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("closePosition sends POST with position id", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({}),
    });
    const api = await loadApi();
    await api.closePosition("pos-1");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/portfolio/positions/pos-1/close",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("resetPortfolio sends POST with initial balance", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ portfolio: {}, message: "reset" }),
    });
    const api = await loadApi();
    await api.resetPortfolio(10000);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/v1/portfolio/reset",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ initial_balance: 10000 }),
      }),
    );
  });

  it("includes Authorization header when key in localStorage", async () => {
    localStorage.setItem("pm-api-key", "test-key");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ data: [], limit: 100, offset: 0 }),
    });
    const api = await loadApi();
    await api.leaderboard(100, 0);
    const call = mockFetch.mock.calls[0];
    const headers = call[1].headers;
    expect(headers["Authorization"]).toBe("Bearer test-key");
  });
});
