import { defineConfig } from "playwright/test";
import base from "./playwright.power-apps.config";
export default defineConfig({ ...base, testMatch: ["google-redirect.spec.ts"] });
