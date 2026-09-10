import { readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const sharedOut = join(process.cwd(), "out", "shared");
const testFiles = readdirSync(sharedOut)
  .filter((name) => name.endsWith(".test.js"))
  .sort()
  .map((name) => join(sharedOut, name));

if (testFiles.length === 0) {
  console.error("No compiled shared client tests found.");
  process.exit(1);
}

const result = spawnSync(process.execPath, ["--test", ...testFiles], {
  stdio: "inherit",
});
process.exit(result.status ?? 1);
