import { defineConfig, mergeConfig } from 'vite';
import base from '../vite.config.ts';

// Keep the real HTTP workflow stable while other workspace files are being edited.
export default defineConfig(async env => mergeConfig(await base(env), {
  cacheDir:'node_modules/.vite-srm-real-backend',
  server:{host:'127.0.0.1',port:5181,strictPort:true,hmr:false,watch:null,
    proxy:{'/api':{target:'http://127.0.0.1:1534',changeOrigin:true},'/uploads':{target:'http://127.0.0.1:1534',changeOrigin:true}}},
}));
