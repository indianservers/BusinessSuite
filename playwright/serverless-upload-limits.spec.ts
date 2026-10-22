import { test, expect } from "../frontend/node_modules/playwright/test";

test("oversized multipart uploads show a useful error before making a request", async ({ page }) => {
  let requests = 0;
  page.on("request", request => { if (request.url().includes("upload-limit-probe")) requests++; });
  await page.goto("/login");
  const result = await page.evaluate(async () => {
    const { api } = await import("/src/services/api.ts");
    const data = new FormData();
    data.append("file", new File([new Uint8Array(3 * 1024 * 1024 + 1)], "too-large.pdf", { type: "application/pdf" }));
    try {
      await api.post("/upload-limit-probe", data);
      return { status: 200, detail: "Unexpected request" };
    } catch (error: any) {
      return { status: error.response?.status, detail: error.response?.data?.detail };
    }
  });
  expect(result.status).toBe(413);
  expect(result.detail).toContain("3 MB upload limit");
  expect(requests).toBe(0);
});
