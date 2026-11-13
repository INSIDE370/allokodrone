import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const out = join(root, "public");
const dist = join(root, "web", "dist");
const tunnel = (process.env.ALLOKO_TUNNEL_URL || process.env.VITE_API_BASE || "https://example-abu-sas-army.trycloudflare.com").replace(
  /\/$/,
  "",
);

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
cpSync(join(out, "index.html"), join(out, "404.html"));

// Admin : GitHub Pages ne peut pas proxifier Python → redirection vers le tunnel
const adminDir = join(out, "admin");
mkdirSync(adminDir, { recursive: true });
const adminTarget = `${tunnel}/admin`;
writeFileSync(
  join(adminDir, "index.html"),
  `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="0;url=${adminTarget}" />
  <link rel="canonical" href="${adminTarget}" />
  <title>Admin — AlloKodrone</title>
  <script>location.replace(${JSON.stringify(adminTarget)})</script>
</head>
<body style="font-family:system-ui;padding:2rem;text-align:center">
  <p>Ouverture de l’administration…</p>
  <p><a href="${adminTarget}">Continuer vers l’admin</a></p>
</body>
</html>
`,
);

console.log(`GitHub Pages prêt → public/ (admin → ${adminTarget})`);
