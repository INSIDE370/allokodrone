import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const out = join(root, "public");

if (existsSync(out)) rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

const dist = join(root, "web", "dist");
if (!existsSync(dist)) {
  throw new Error("web/dist manquant — lance d'abord npm run build:web");
}

cpSync(dist, out, { recursive: true });

for (const folder of ["images", "css", "js", "videos", "fonts"]) {
  const src = join(root, folder);
  if (!existsSync(src)) continue;
  cpSync(src, join(out, folder), { recursive: true });
}

const menu = join(root, "menu.pdf");
if (existsSync(menu)) cpSync(menu, join(out, "menu.pdf"));

console.log(`Vercel public prêt → ${out}`);
