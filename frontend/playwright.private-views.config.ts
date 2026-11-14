import {defineConfig} from 'playwright/test';
export default defineConfig({testDir:'../playwright',testMatch:['crm-task-views.spec.ts','hrms-ticket-views.spec.ts','saved-view-review.spec.ts','form-action-review.spec.ts','workload-source.spec.ts','calendar-action-review.spec.ts','time-action-review.spec.ts','timer-action-review.spec.ts'],timeout:45_000,
 expect:{timeout:10_000},use:{baseURL:'http://127.0.0.1:5186',trace:'retain-on-failure'}});
