import { writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
const commit = process.env.SUITE_RELEASE_SHA || process.env.VERCEL_GIT_COMMIT_SHA || execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim();
if (!/^[a-f0-9]{40}$/.test(commit)) throw new Error("Release commit must be a full Git SHA");
const candidate = process.env.SUITE_RELEASE_CANDIDATE;
if (candidate && !/^[a-f0-9]{64}$/.test(candidate)) throw new Error("Release candidate must be a SHA-256 fingerprint");
await writeFile(resolve("dist/release.json"), JSON.stringify({ commit, ...(candidate ? { candidate } : {}) }) + "\n");
