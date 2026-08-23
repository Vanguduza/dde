/**
 * Prototype Gallery unit tests (playbook §5.0 P2, §5.3 sandbox law).
 *
 * Pure string/model tests — no VS Code host, no Core, runs on Windows via
 * node --test. Run: npm test.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  GALLERY_IFRAME_SANDBOX,
  GALLERY_PREVIEW_CSP,
  buildGalleryModel,
  galleryScreenFromRelPath,
  parseFlowsManifest,
  previewGalleryChrome,
  previewGalleryPage,
  wrapScreenSrcdoc,
} from "./ui/previewGallery";

describe("galleryScreenFromRelPath", () => {
  it("splits screen name and state suffix", () => {
    const s = galleryScreenFromRelPath("screens/overview.ready.html");
    assert.equal(s.name, "overview");
    assert.equal(s.state, "ready");
  });

  it("yields no state when the file name has no suffix", () => {
    const s = galleryScreenFromRelPath("screens/overview.html");
    assert.equal(s.name, "overview");
    assert.equal(s.state, undefined);
  });

  it("treats a leading dot as a dotfile, not a state", () => {
    const s = galleryScreenFromRelPath("screens/.hidden.html");
    assert.equal(s.name, ".hidden");
    assert.equal(s.state, undefined);
  });
});

describe("parseFlowsManifest", () => {
  it("parses a valid manifest into flows", () => {
    const flows = parseFlowsManifest(`{
      "version": 1,
      "flows": [
        {
          "id": "start-mission",
          "entry": "overview.ready.html",
          "steps": [
            { "from": "overview.ready.html", "on": "[data-cmd='startMission']", "to": "mission-control.running.html" }
          ]
        }
      ]
    }`);
    assert.equal(flows.length, 1);
    assert.equal(flows[0].id, "start-mission");
    assert.equal(flows[0].entry, "overview.ready.html");
    assert.equal(flows[0].steps.length, 1);
    assert.equal(flows[0].steps[0].to, "mission-control.running.html");
  });

  it("returns empty on malformed JSON", () => {
    assert.deepEqual(parseFlowsManifest("{not json"), []);
  });

  it("returns empty when flows is not an array", () => {
    assert.deepEqual(parseFlowsManifest(`{ "flows": "nope" }`), []);
  });

  it("drops steps with non-string fields instead of failing", () => {
    const flows = parseFlowsManifest(`{
      "flows": [
        { "id": "f", "entry": "a.html", "steps": [ { "from": 1, "on": "x", "to": "b.html" } ] }
      ]
    }`);
    assert.equal(flows.length, 1);
    assert.equal(flows[0].steps.length, 0);
  });
});

describe("buildGalleryModel", () => {
  it("reports no-directory when the root is absent", () => {
    assert.equal(buildGalleryModel({ exists: false, entries: [] }), "no-directory");
  });

  it("reports empty-directory when no screens and no flows exist", () => {
    assert.equal(
      buildGalleryModel({ exists: true, entries: [] }),
      "empty-directory",
    );
  });

  it("collects only screens/*.html as screens", () => {
    const model = buildGalleryModel({
      exists: true,
      entries: [
        { relPath: "screens/overview.ready.html", content: "<html></html>" },
        { relPath: "screens/notes.md", content: "not a screen" },
        { relPath: "flows.json", content: `{ "flows": [] }` },
      ],
    });
    assert.ok(typeof model !== "string");
    assert.equal(model.screens.length, 1);
    assert.equal(model.screens[0].relPath, "screens/overview.ready.html");
    assert.equal(model.flows.length, 0);
  });

  it("renders a gallery for a lone valid flows.json", () => {
    const model = buildGalleryModel({
      exists: true,
      entries: [{ relPath: "flows.json", content: `{ "flows": [] }` }],
    });
    assert.ok(typeof model !== "string");
  });
});

describe("sandbox law", () => {
  it("iframe sandbox is allow-scripts only — never allow-same-origin", () => {
    assert.equal(GALLERY_IFRAME_SANDBOX, "allow-scripts");
    const html = previewGalleryChrome({
      screens: [
        { relPath: "screens/a.ready.html", name: "a", state: "ready" },
      ],
      flows: [],
    });
    assert.match(html, /sandbox="allow-scripts"/);
    assert.doesNotMatch(html, /allow-same-origin/);
  });

  it("preview CSP has no network sources", () => {
    assert.equal(
      GALLERY_PREVIEW_CSP,
      "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:",
    );
  });

  it("wrapScreenSrcdoc injects the CSP when the page lacks one", () => {
    const out = wrapScreenSrcdoc("<html><head></head><body>hi</body></html>");
    assert.match(out, /Content-Security-Policy/);
    assert.match(out, /default-src 'none'/);
  });

  it("wrapScreenSrcdoc preserves an existing CSP instead of duplicating", () => {
    const page =
      '<html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'"></head><body>x</body></html>';
    const out = wrapScreenSrcdoc(page);
    assert.equal(out.match(/Content-Security-Policy/g)?.length, 1);
  });

  it("wraps fragment input in a full document with the CSP", () => {
    const out = wrapScreenSrcdoc("<p>fragment</p>");
    assert.match(out, /<!DOCTYPE html>/);
    assert.match(out, /<p>fragment<\/p>/);
    assert.match(out, /Content-Security-Policy/);
  });
});

describe("gallery chrome copy and structure", () => {
  it("empty gallery shows a factual title with no helper essay", () => {
    const html = previewGalleryChrome("no-directory");
    assert.match(html, /No prototypes yet/);
    assert.match(html, /role="status"/);
    assert.doesNotMatch(html, /!/);
    assert.doesNotMatch(html, /[Ww]elcome|[Ss]imply|[Ee]asily/);
  });

  it("live gallery lists screens and exposes the reduced-motion toggle", () => {
    const html = previewGalleryChrome({
      screens: [
        { relPath: "screens/overview.ready.html", name: "overview", state: "ready" },
      ],
      flows: [{ id: "f1", entry: "overview.ready.html", steps: [] }],
    });
    assert.match(html, /data-screen="screens\/overview\.ready\.html"/);
    assert.match(html, /id="pg-reduced-motion"/);
    assert.match(html, /Reduce motion/);
    assert.match(html, /Flows manifest/);
  });

  it("full page carries the page CSP and skip-link", () => {
    const html = previewGalleryPage("no-directory");
    assert.match(html, /Content-Security-Policy/);
    assert.match(html, /class="skip-link"/);
    assert.match(html, /data-surface="preview-gallery"/);
  });
});
