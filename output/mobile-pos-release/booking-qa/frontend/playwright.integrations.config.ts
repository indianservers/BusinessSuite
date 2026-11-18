import { defineConfig } from "playwright/test";
import base from "./playwright.power-approvals.config";
export default defineConfig({ ...base, testMatch:["power-integrations-live.spec.ts"],outputDir:"../.tmp/integration-browser",timeout:90_000 });
