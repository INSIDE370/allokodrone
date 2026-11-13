import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const tunnel = (process.env.ALLOKO_TUNNEL_URL || "https://example-abu-sas-army.trycloudflare.com").replace(
  /\/$/,
  "",
);

const env = {
  ...process.env,
  VITE_BASE: "/allokodrone/",
  VITE_API_BASE: tunnel,
};

const build = spawnSync("npm", ["--prefix", "web", "run", "build"], {
  cwd: root,
  env,
  stdio: "inherit",
  shell: true,
});
if (build.status !== 0) process.exit(build.status || 1);

const prepare = spawnSync("node", ["scripts/prepare-github-pages.mjs"], {
  cwd: root,
  env,
  stdio: "inherit",
  shell: true,
});
process.exit(prepare.status || 0);
