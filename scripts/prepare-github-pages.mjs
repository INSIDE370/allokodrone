import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const out = join(root, "public");
const dist = join(root, "web", "dist");

if (!existsSync(dist)) throw new Error("web/dist manquant");
if (existsSync(out)) rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
cpSync(dist, out, { recursive: true });

for (const folder of ["images", "css", "js", "videos", "fonts"]) {
  const src = join(root, folder);
  if (existsSync(src)) cpSync(src, join(out, folder), { recursive: true });
}
if (existsSync(join(root, "menu.pdf"))) cpSync(join(root, "menu.pdf"), join(out, "menu.pdf"));

// SPA fallback for GitHub Pages
writeFileSync(join(out, "404.html"), existsSync(join(out, "index.html")) ? "" : "");
cpSync(join(out, "index.html"), join(out, "404.html"));

console.log("GitHub Pages prêt → public/");
