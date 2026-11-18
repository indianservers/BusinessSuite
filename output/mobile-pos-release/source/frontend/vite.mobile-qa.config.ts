import { defineConfig } from 'vite';
import base from './vite.config';
export default defineConfig(async env => ({...(typeof base === 'function' ? await base(env) : base),cacheDir:'../.tmp/mobile-enhancements-vite'}));
