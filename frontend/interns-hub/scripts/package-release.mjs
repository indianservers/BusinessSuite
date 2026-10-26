import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const { values } = parseArgs({ options: {
  output: { type: "string" },
  "api-base-url": { type: "string" },
  "hrms-login-url": { type: "string" },
  "firebase-config-file": { type: "string" },
} });
if (!values.output || !values["api-base-url"] || !values["hrms-login-url"]) {
  throw new Error("Provide --output, --api-base-url and --hrms-login-url. Build with npm run build first.");
}
for (const key of ["api-base-url", "hrms-login-url"]) {
  const url = new URL(values[key]);
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash) {
    throw new Error(`${key} must be a public HTTPS URL without credentials, query or fragment`);
  }
}
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = resolve(root, "dist");
let firebaseConfig;
if (values["firebase-config-file"]) {
  firebaseConfig = JSON.parse(await readFile(resolve(values["firebase-config-file"]), "utf8"));
  const allowed = new Set(["apiKey","authDomain","projectId","storageBucket","messagingSenderId","appId","measurementId"]);
  if (Object.keys(firebaseConfig).some(key=>!allowed.has(key)) || ["apiKey","authDomain","projectId","appId"].some(key=>typeof firebaseConfig[key] !== "string" || !firebaseConfig[key])) {
    throw new Error("Provide only the public Firebase web configuration, with apiKey, authDomain, projectId and appId");
  }
}
await readFile(resolve(dist, "index.html"));
const output = resolve(values.output, ".vercel/output");
// Refuse to overwrite a previous release or a source tree.
await mkdir(dirname(output), { recursive: true });
await mkdir(output);
await cp(dist, resolve(output, "static"), { recursive: true });
await writeFile(resolve(output, "static/config.js"),
  `window.__INTERNHUB_CONFIG__ = ${JSON.stringify({
    apiBaseUrl: values["api-base-url"], hrmsLoginUrl: values["hrms-login-url"], firebaseConfig,
  }, null, 2)};\n`);
await writeFile(resolve(output, "config.json"), JSON.stringify({
  version: 3,
  routes: [
    { src: "/(.*)", headers: { "X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin" }, continue: true },
    { src: "/config\\.js", headers: { "Cache-Control": "no-store" }, continue: true },
    { src: "/release\\.json", headers: { "Cache-Control": "no-store" }, continue: true },
    { handle: "filesystem" },
    { src: "/api(?:/.*)?", status: 404 },
    { src: "/.*", dest: "/index.html" },
  ],
}, null, 2) + "\n");
console.log(`Interns Hub release packaged at ${resolve(values.output)}. Serve .vercel/output/static on any static host, or deploy with vercel --prebuilt.`);
