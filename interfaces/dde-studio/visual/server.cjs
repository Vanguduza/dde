/**
 * Static preview server for the visual gate (EDR-0008).
 *
 * Serves each fixture gallery screen through the same wrapScreenSrcdoc CSP
 * wrapper the Prototype Gallery webview applies inside its sandboxed iframe,
 * so screenshot goldens see exactly what the webview renders — not a
 * parallel rendering path. Node stdlib http only; requires `npm run compile`
 * first (imports the emitted out/shared modules).
 */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const { buildGalleryModel, previewGalleryPage, wrapScreenSrcdoc } = require(
  "../out/shared/ui/previewGallery",
);
const { tokenCssRoot } = require("../out/shared/ui/tokens");

const PORT = Number(process.env.VISUAL_PORT || 4173);
const HOST = "127.0.0.1";
const FIXTURES = path.join(__dirname, "fixtures");

function readFixtures() {
  const entries = [];
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir)) {
      const full = path.join(dir, name);
      if (fs.statSync(full).isDirectory()) {
        walk(full);
      } else {
        entries.push({
          relPath: path.relative(FIXTURES, full).split(path.sep).join("/"),
          content: fs.readFileSync(full, "utf8"),
        });
      }
    }
  };
  walk(FIXTURES);
  return entries;
}

/** Screens whose CSS declares keyframes get an extra reduced-motion pass. */
function collectAnimatedScreens(entries) {
  return entries
    .filter((e) => e.relPath.startsWith("screens/") && /\.html$/i.test(e.relPath))
    .filter((e) => /@keyframes/i.test(e.content))
    .map((e) => e.relPath);
}

function send(res, status, body, type) {
  res.writeHead(status, {
    "Content-Type": type,
    "Cache-Control": "no-store",
  });
  res.end(body);
}

function screenHref(relPath) {
  return `/screen/${encodeURI(relPath)}`;
}

function renderIndex() {
  const entries = readFixtures();
  const model = buildGalleryModel({ exists: true, entries });
  let page =
    typeof model === "string"
      ? `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><style>${tokenCssRoot()}body{background:var(--bg);color:var(--fg);font-family:sans-serif}</style></head><body>No screens yet</body></html>`
      : previewGalleryPage(model);
  // The webview drives screen opens through postMessage; this server wires
  // the same data-screen attributes to plain navigation instead.
  page = page.replace(
    "</body>",
    `<script>
      document.addEventListener("click", (event) => {
        const el = event.target instanceof Element
          ? event.target.closest("[data-screen]")
          : null;
        if (el) location.href = "/screen/" + encodeURIComponent(el.getAttribute("data-screen"));
      });
    </script></body>`,
  );
  return { page, entries };
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? "/", `http://${HOST}:${PORT}`);
  if (url.pathname === "/" || url.pathname === "/index.json") {
    const { entries } = renderIndex();
    if (url.pathname === "/index.json") {
      send(res, 200, JSON.stringify({
        screens: entries.filter((e) => /^screens\/.+\.html$/i.test(e.relPath)).map((e) => e.relPath),
        animated: collectAnimatedScreens(entries),
      }), "application/json");
      return;
    }
    send(res, 200, renderIndex().page, "text/html; charset=utf-8");
    return;
  }
  const match = url.pathname.match(/^\/screen\/(.+)$/);
  if (match) {
    const relPath = decodeURIComponent(match[1]).replace(/\\/g, "/");
    if (!/^screens\/[^/]+\.html$/i.test(relPath)) {
      send(res, 404, "not found", "text/plain");
      return;
    }
    const full = path.join(FIXTURES, ...relPath.split("/"));
    try {
      send(res, 200, wrapScreenSrcdoc(fs.readFileSync(full, "utf8")), "text/html; charset=utf-8");
    } catch {
      send(res, 404, "not found", "text/plain");
    }
    return;
  }
  send(res, 404, "not found", "text/plain");
});

server.listen(PORT, HOST, () => {
  process.stdout.write(`visual preview server on http://${HOST}:${PORT}\n`);
});
