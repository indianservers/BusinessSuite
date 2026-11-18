import { defineConfig } from 'playwright/test';
import base from './playwright.payroll-delivery.config';
export default defineConfig({ ...base, testMatch: 'payroll-qa-live.spec.ts', timeout: 90000,
  outputDir: '../.tmp/payroll-qa-live', use: { ...base.use, trace: 'on' } });
