import { expect, test, type Page } from "@playwright/test";

const FIXTURE = "/visual/live-loop.html";

async function openCursorChat(page: Page): Promise<void> {
  await page.goto(FIXTURE);
  await expect(page.getByTestId("dde-shell")).toBeVisible();
  await page.getByRole("button", { name: "Show DDE AI Chat" }).click();
  await page.getByTestId("chat-new").click();
  await expect(page.getByTestId("chat-mode-ask")).toHaveAttribute("aria-pressed", "true");
}

async function selectHero(page: Page) {
  const hero = page
    .frameLocator("iframe.dde-preview-frame")
    .locator('[data-dde-pxg-key="screens/checkout#hero"]');
  await hero.click();
  await expect(page.getByTestId("chat-selection-chip")).toContainText("hero");
  return hero;
}

test.describe("Cursor-class DDE AI Chat", () => {
  test("Ask refuses, Plan prepares, Execute-through-plan mutates and reverifies", async ({ page }) => {
    await openCursorChat(page);
    let hero = await selectHero(page);

    await page.getByTestId("chat-input").fill("set the spacing to space4");
    await page.getByTestId("chat-send").click();
    await expect(page.getByTestId("chat-thread")).toContainText("MODE_READ_ONLY");
    await expect(hero).toContainText("Hero space2");

    await page.getByTestId("chat-mode-plan").click();
    await expect(page.getByTestId("chat-mode-plan")).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("chat-input").fill("set the spacing to space4");
    await page.getByTestId("chat-send").click();
    await expect(page.getByTestId("chat-plan-panel")).toContainText("Change spacing");
    await expect(page.getByTestId("chat-plan-panel")).toContainText("READY");
    await expect(hero).toContainText("Hero space2");

    await page.getByTestId("chat-plan-approve").click();
    await expect(page.getByTestId("chat-plan-panel")).toContainText("APPROVED");
    await page.getByTestId("chat-plan-run-1").click();

    hero = page
      .frameLocator("iframe.dde-preview-frame")
      .locator('[data-dde-pxg-key="screens/checkout#hero"]');
    await expect(hero).toContainText("Hero space4");
    await expect(page.getByTestId("preview-badge")).toHaveText("LIVE");
    await expect(page.getByTestId("chat-plan-panel")).toContainText("COMPLETED");
    await expect(
      page.getByTestId("candidate-verification-00000000-0000-0000-0000-000000000020"),
    ).toHaveText("VERIFY PASSED");
  });
  test("history search, rename and branching operate on durable threads", async ({ page }) => {
    await openCursorChat(page);

    const title = page.getByLabel("Conversation title");
    await title.fill("Checkout implementation plan");
    await page.getByRole("button", { name: "Rename" }).click();
    await expect(page.getByTestId("chat-thread")).toContainText("Checkout implementation plan");

    await page.getByTestId("chat-history-toggle").click();
    await page.getByLabel("Search chat history").fill("Earlier");
    await page.getByTestId("chat-history").getByRole("button", { name: "Search" }).click();
    await expect(page.getByTestId("chat-history")).toContainText("Earlier checkout exploration");

    await page.getByTestId("chat-history-toggle").click();
    await page.getByTestId("chat-branch").click();
    await expect(page.getByTestId("chat-thread")).toContainText("branch");

    const commands = await page.evaluate(() =>
      (window as unknown as { __ddeTestBridge: { sentCommands: Array<{ commandType: string }> } })
        .__ddeTestBridge.sentCommands.map((item) => item.commandType),
    );
    expect(commands).toContain("frontend.chat.rename");
    expect(commands).toContain("frontend.chat.branch");
  });

  test("native attachment reservation and opaque-token upload bind files to a turn", async ({ page }) => {
    await openCursorChat(page);
    await page.getByTestId("chat-attach").click();
    await expect(page.getByTestId("chat-attachment-tray")).toContainText("requirements.md");
    await expect(page.getByTestId("chat-pending-attachments")).toContainText("1 file(s)");

    await page.getByTestId("chat-input").fill("how much coverage do we have?");
    await page.getByTestId("chat-send").click();
    await expect(page.getByTestId("chat-thread")).toContainText("1 attachment(s)");
    await expect(page.getByTestId("chat-attachment-tray")).toHaveCount(0);
  });
  test("context pins and checkpoints preserve governed conversation state", async ({ page }) => {
    await openCursorChat(page);
    await page.getByRole("tab", { name: "context" }).click();
    await page.getByLabel("Pin context reference").fill("file:src/Checkout.tsx");
    await page.getByRole("button", { name: "Pin" }).click();
    await expect(page.getByTestId("chat-context-panel")).toContainText("file:src/Checkout.tsx");
    await expect(page.getByTestId("chat-context-panel")).toContainText("512 / 24,000 tokens");

    await page.getByTestId("chat-mode-plan").click();
    await page.getByRole("tab", { name: "checkpoints" }).click();
    await page.getByLabel("Checkpoint note").fill("before plan edits");
    await page.getByRole("button", { name: "Checkpoint" }).click();
    await expect(page.getByTestId("chat-checkpoint-panel")).toContainText("before plan edits");

    await page.getByTestId("chat-mode-ask").click();
    await page.getByRole("button", { name: "Restore context" }).click();
    await expect(page.getByTestId("chat-mode-plan")).toHaveAttribute("aria-pressed", "true");
  });

  test("changed-file review, activity stop and model availability are visible and actionable", async ({ page }) => {
    await openCursorChat(page);

    await page.getByTestId("chat-model-select").selectOption("profile.claude_code_cli");
    await expect(page.getByTestId("chat-model-select")).toHaveValue("profile.claude_code_cli");

    await page.getByRole("tab", { name: "activity" }).click();
    await expect(page.getByTestId("chat-activity-panel")).toContainText("APPROVAL_REQUIRED").catch(() => {});
    await page.getByRole("button", { name: "Stop" }).click();
    await expect(page.getByTestId("chat-activity-panel")).toContainText("CANCELLED");

    await page.getByRole("tab", { name: "changes" }).click();
    const changes = page.getByTestId("chat-changes-panel");
    await expect(changes).toContainText("src/Checkout.tsx");
    await changes.getByRole("button", { name: "Accept" }).click();
    await expect(changes).toContainText("ACCEPTED");
  });
});
