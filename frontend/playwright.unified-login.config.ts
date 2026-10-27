import { defineConfig } from "playwright/test";
import approvals from "./playwright.power-approvals.config";
export default defineConfig({ ...approvals, testMatch: ["unified-login-live.spec.ts"], outputDir: "../.tmp/unified-login-browser" });
