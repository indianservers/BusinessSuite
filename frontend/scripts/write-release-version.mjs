import { writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
const commit = process.env.SUITE_RELEASE_SHA || execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim();
if (!/^[a-f0-9]{40}$/.test(commit)) throw new Error("Release commit must be a full Git SHA");
await writeFile(resolve("dist/release.json"), JSON.stringify({ commit }) + "\n");
