import { defineConfig } from "playwright/test";
import base from "./playwright.power-apps.config";

// Full-stack contract audit: needs the backend Python dependencies installed.
export default defineConfig({ ...base, testMatch: ["power-module-options.spec.ts"], timeout: 120_000 });
