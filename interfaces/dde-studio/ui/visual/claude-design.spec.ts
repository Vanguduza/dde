import { expect, test, type Page } from "@playwright/test";

/**
 * DDE-069 — the `Claude /design` toolbar control.
 *
 * The control has exactly one enable condition: a provider the Gateway
 * reports as CERTIFIED. Everything else is a typed unavailable state that
 * names what is actually wrong. These tests assert both halves, because a
 * control that only ever renders one of them proves nothing about which
 * one it would render.
 *
 * The second property under test is that the button is not a second chat.
 * Pressing it must produce a `/design` turn in the same Universal DDE Chat
 * conversation the composer writes to, and must not send
 * `frontend.design.request` around it.
 */

const FIXTURE = "/visual/live-loop.html";

/** The chat panel is collapsed by default; the control does not open it. */
async function showChat(page: Page): Promise<void> {
  await expect(page.getByTestId("dde-shell")).toBeVisible();
  await page.getByRole("button", { name: "Show DDE AI Chat" }).click();
  await page.getByTestId("chat-new").click();
  await expect(page.getByTestId("chat-mode-ask")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
}

test.describe("Claude /design control", () => {
  test("is disabled with a typed reason when no transport is certified", async ({
    page,
  }) => {
    await page.goto(FIXTURE);
    const button = page.getByTestId("claude-design");
    await expect(button).toBeVisible();
    await expect(button).toBeDisabled();
    await expect(button).toHaveAttribute("data-provider-state", "NOT_CERTIFIED");
    const reason = await button.getAttribute("title");
    expect(reason).toContain("no certified design provider transport");
  });

  test("distinguishes a signed-out host from an absent transport", async ({
    page,
  }) => {
    await page.goto(`${FIXTURE}?design=auth`);
    const button = page.getByTestId("claude-design");
    await expect(button).toBeDisabled();
    await expect(button).toHaveAttribute("data-provider-state", "AUTH_REQUIRED");
    const reason = await button.getAttribute("title");
    expect(reason).toContain("AUTH_REQUIRED");
    expect(reason).toContain("claude auth login");
  });

  test("enables only when the provider is CERTIFIED", async ({ page }) => {
    await page.goto(`${FIXTURE}?design=certified`);
    const button = page.getByTestId("claude-design");
    await expect(button).toBeEnabled();
    await expect(button).toHaveAttribute("data-provider-state", "CERTIFIED");
    const reason = await button.getAttribute("title");
    expect(reason).toContain("CERTIFIED");
    expect(reason).not.toContain("unavailable");
  });

  test("routes through the shared DDE chat, never a second conversation", async ({
    page,
  }) => {
    await page.goto(`${FIXTURE}?design=certified`);
    await showChat(page);
    await page.getByTestId("chat-mode-execute").click();
    await page.getByTestId("claude-design").click();

    // The turn lands in the one conversation the composer uses.
    const thread = page.getByTestId("chat-thread");
    await expect(thread).toContainText("/design three alternative directions");
    await expect(thread).toContainText("3 direction(s) generated");

    const commands = await page.evaluate(
      () =>
        (
          window as unknown as {
            __ddeTestBridge: { sentCommands: Array<{ commandType: string }> };
          }
        ).__ddeTestBridge.sentCommands.map((item) => item.commandType),
    );
    expect(commands).toContain("frontend.design.provider_status");
    expect(commands).toContain("frontend.chat.send");
    // The control must not reach the DesignGateway around the conversation,
    // and must not open a second thread for itself.
    expect(commands).not.toContain("frontend.design.request");
    expect(commands.filter((item) => item === "frontend.chat.open")).toHaveLength(1);
  });

  test("renders persisted directions and Try Live enters the ordinary candidate preview loop", async ({ page }) => {
    await page.goto(`${FIXTURE}?design=certified`);
    await showChat(page);
    await page.getByTestId("chat-mode-execute").click();
    await page.getByTestId("claude-design").click();

    const directions = page.getByTestId("design-directions");
    await expect(directions).toBeVisible();
    await expect(page.getByTestId("design-direction-A")).toContainText("GENERATED");
    await expect(page.getByTestId("design-direction-B")).toContainText("GENERATED");
    await expect(page.getByTestId("design-direction-C")).toContainText("GENERATED");

    await page.getByTestId("design-try-live-A").click();
    await expect(page.getByTestId("design-try-live-A")).toHaveText("Tried Live");
    await expect(page.getByTestId("design-direction-B")).toContainText("GENERATED");
    await expect(page.getByTestId("design-direction-C")).toContainText("GENERATED");

    // Direction A carries spacing=space6 in this deterministic provider fixture.
    // Prove the selected artifact, rather than another candidate or stale preview,
    // is what reached the browser-backed LIVE surface.
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    const preview = page.frameLocator('iframe[title^="Candidate preview "]');
    await expect(preview.locator('[data-spacing="space6"]')).toContainText("Hero space6");
    await expect(page.locator('[data-testid^="candidate-verification-"]')).toContainText("VERIFY PASSED");

    const commands = await page.evaluate(() =>
      (window as unknown as { __ddeTestBridge: { sentCommands: Array<{ commandType: string }> } })
        .__ddeTestBridge.sentCommands.map((item) => item.commandType),
    );
    expect(commands).toContain("frontend.design.try_live");
    expect(commands).toContain("frontend.preview.start");
    expect(commands).toContain("frontend.preview.set_state");
    expect(commands).toContain("frontend.verification.run");
    expect(commands).not.toContain("frontend.design.request");
  });

  test("a read-only conversation refuses /design on the mode, not the provider", async ({
    page,
  }) => {
    await page.goto(`${FIXTURE}?design=certified`);
    await showChat(page);
    await page.getByTestId("claude-design").click();
    const thread = page.getByTestId("chat-thread");
    await expect(thread).toContainText("Ask mode is read-only");
  });
});
