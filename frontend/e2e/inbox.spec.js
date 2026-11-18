import { expect, test } from "@playwright/test";
import { PAGES_URL } from "../playwright.config.js";

// One shared backend per run, so these run in order and build on each other.
test.describe.configure({ mode: "serial" });

const library = (page) => page.getByRole("complementary", { name: "Your library" });
const row = (page, title) => library(page).getByRole("listitem").filter({ hasText: title }).first();
const pipeline = (page, title) => row(page, title).getByRole("list", { name: "Ingestion pipeline" });

test("starts empty and connected", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Connected")).toBeVisible();
  await expect(page.getByText("Nothing saved yet")).toBeVisible();
  await expect(page.getByText("Save a note or a link first")).toBeVisible();
});

test("validates input before calling the API", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Save note" }).click();
  await expect(page.getByRole("alert")).toHaveText("Write something to save.");

  await page.getByRole("radio", { name: "Link" }).check({ force: true });
  await page.getByRole("textbox", { name: "Page link" }).fill("notalink");
  await page.getByRole("button", { name: "Save link" }).click();
  await expect(page.getByRole("alert")).toHaveText("Enter the full link, starting with https://");

  const askButton = page.getByRole("button", { name: "Ask" });
  await expect(askButton).toBeDisabled(); // nothing to send yet
  await page.getByRole("textbox", { name: "What do you want to know?" }).fill("   ");
  await expect(askButton).toBeDisabled(); // whitespace doesn't count
  await page.getByRole("textbox", { name: "What do you want to know?" }).press("Enter");
  await expect(page.getByRole("article")).toHaveCount(0);
  await page.getByRole("textbox", { name: "What do you want to know?" }).fill("Ready?");
  await expect(askButton).toBeEnabled();
  await page.getByRole("textbox", { name: "What do you want to know?" }).fill("");

  await expect(page.getByText("Nothing saved yet")).toBeVisible(); // nothing was ingested
});

test("note: every pipeline step runs and is shown live", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "Note" })
    .fill("Retro notes\n\nReleases slipped because staging was shared by three teams. Each team now gets its own preview environment.");
  await page.getByRole("button", { name: "Save note" }).click();
  await expect(page.getByText("Note saved")).toBeVisible();

  // Live: the slow step is visible while it runs.
  await expect(row(page, "Retro notes").getByText("Creating vectors (3/4)")).toBeVisible();
  await expect(row(page, "Retro notes").getByRole("progressbar")).toBeVisible();

  // Done: all four steps complete with details.
  await expect(row(page, "Retro notes").getByText("1 chunk", { exact: true })).toBeVisible();
  const steps = pipeline(page, "Retro notes").getByRole("listitem");
  await expect(steps).toHaveCount(4);
  await expect(steps.nth(0)).toContainText("Received");
  await expect(steps.nth(0)).toContainText("Note received");
  await expect(steps.nth(1)).toContainText("1 chunk of up to 800 characters");
  await expect(steps.nth(2)).toContainText("1 vector with");
  await expect(steps.nth(3)).toContainText("Saved 1 chunk with its vector");
});

test("link: the page is loaded on the server, then chunked, embedded and stored", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("radio", { name: "Link" }).check({ force: true });
  await page.getByRole("textbox", { name: "Page link" }).fill(`${PAGES_URL}/article.html`);
  await page.getByRole("button", { name: "Save link" }).click();
  await expect(page.getByText("Link saved")).toBeVisible();

  const item = row(page, "Connection Pooling Guide");
  await expect(item.getByText(/chunks?$/)).toBeVisible();
  const steps = pipeline(page, "Connection Pooling Guide").getByRole("listitem");
  await expect(steps).toHaveCount(5);
  await expect(steps.nth(1)).toContainText("Loading page");
  await expect(steps.nth(1)).toContainText("characters from 127.0.0.1");
  await expect(steps.nth(4)).toContainText("Storing in database");
  await expect(item).toContainText("PgBouncer sits between the application and Postgres");
  await expect(item).not.toContainText("Copyright Example Corp");
});

test("link: a broken page fails at Loading page and later steps are skipped", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("radio", { name: "Link" }).check({ force: true });
  await page.getByRole("textbox", { name: "Page link" }).fill(`${PAGES_URL}/missing.html`);
  await page.getByRole("button", { name: "Save link" }).click();

  const item = row(page, "127.0.0.1");
  await expect(item.getByText("Failed at Loading page")).toBeVisible();
  const steps = pipeline(page, "127.0.0.1").getByRole("listitem");
  await expect(steps.nth(1)).toContainText("The page returned HTTP 404.");
  await expect(steps.nth(2)).toContainText("Skipped");
  await expect(steps.nth(4)).toContainText("Skipped");
});

test("chat: answers cite sources, and citations highlight the passage and the library item", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Searching 2 saved items")).toBeVisible();

  await page.getByRole("textbox", { name: "What do you want to know?" }).fill("How does PgBouncer transaction pooling work?");
  await page.getByRole("button", { name: "Ask" }).click();

  const thread = page.getByRole("region", { name: "Conversation" });
  await expect(thread.getByRole("heading", { name: "How does PgBouncer transaction pooling work?" })).toBeVisible();
  const answer = thread.getByRole("article", { name: "Answer" });
  const firstCitation = answer.getByRole("link", { name: "Source 1" });
  await expect(firstCitation).toBeVisible();
  const firstSource = answer.locator('li[id^="source-"]').first();
  await expect(firstSource).toContainText("Connection Pooling Guide");
  await expect(firstSource).toContainText("% match");

  await firstCitation.hover();
  await expect(firstSource.locator("mark")).toHaveClass(/bg-marker/);
  await expect(row(page, "Connection Pooling Guide")).toHaveClass(/ring-1/);

  const toggle = firstSource.getByRole("button");
  await expect(toggle).toHaveText("Show full passage");
  await toggle.click();
  await expect(toggle).toHaveText("Show less");
});

test("chat: follow-ups continue the same thread and are searched in context", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "What do you want to know?" }).fill("How does PgBouncer transaction pooling work?");
  await page.getByRole("button", { name: "Ask" }).click();
  const thread = page.getByRole("region", { name: "Conversation" });
  await expect(thread.getByRole("article", { name: "Answer" })).toHaveCount(1);

  await page.getByRole("textbox", { name: "Ask a follow-up question" }).fill("and what should we monitor?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("status", { name: "Searching your library" })).toBeVisible(); // book loader while answering

  await expect(thread.getByRole("article", { name: "Answer" })).toHaveCount(2);
  const followUp = thread.getByRole("region", { name: "Question: and what should we monitor?" });
  await expect(followUp.getByText(/Searched for/)).toContainText("How does PgBouncer transaction pooling work? and what should we monitor?");
  await expect(followUp.getByRole("link", { name: "Source 1" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Ask a follow-up question" })).toHaveValue(""); // cleared for the next one
});

test("chat: New chat starts a separate conversation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "What do you want to know?" }).fill("Why did releases slip?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("article", { name: "Answer" })).toHaveCount(1);

  await page.getByRole("button", { name: "New chat" }).click();
  await expect(page.getByRole("heading", { name: "What do you want to know?" })).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(0);

  // Small talk: a friendly reply, no sources and no "no match" note.
  await page.getByRole("textbox", { name: "What do you want to know?" }).fill("Hey, how are you?");
  await page.getByRole("button", { name: "Ask" }).click();
  const replies = page.getByRole("article", { name: "Answer" });
  await expect(replies).toHaveCount(1); // previous thread not carried over
  await expect(replies.first()).toHaveAttribute("data-kind", "small_talk");
  await expect(replies.first()).toContainText("Ask me anything about your saved notes and links.");
  await expect(replies.first()).not.toContainText("No saved passage matched");

  // Off-topic question: says the library doesn't cover it and suggests what to do.
  await page.getByRole("textbox", { name: "Ask a follow-up question" }).fill("zebra giraffe safari?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(replies).toHaveCount(2);
  await expect(replies.nth(1)).toHaveAttribute("data-kind", "not_found");
  await expect(replies.nth(1)).toContainText("Your saved items don't cover that.");
  await expect(replies.nth(1)).toContainText("Try rephrasing, or add a note or link about this in the sidebar.");
  await expect(replies.nth(1).getByRole("link", { name: /Source/ })).toHaveCount(0);
});

test("saved items survive a page reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("tab", { name: /Library/ })).toContainText("3");
  await expect(row(page, "Retro notes")).toBeVisible();
  await expect(row(page, "Connection Pooling Guide")).toBeVisible();
});

test("history: conversations are saved, reopened, continued and deleted", async ({ page }) => {
  await page.goto("/");
  const historyTab = page.getByRole("tab", { name: /History/ });
  await expect(historyTab).toContainText("4"); // four conversations started above

  await historyTab.click();
  const entries = page.getByRole("tabpanel").getByRole("listitem");
  await expect(entries.first()).toContainText("Hey, how are you?"); // most recent first
  const threadEntry = entries.filter({ hasText: "How does PgBouncer transaction pooling work?" }).filter({ hasText: "2 questions" });
  await expect(threadEntry).toHaveCount(1);

  // Reopen: every turn comes back, nothing new is created.
  const open = threadEntry.getByRole("button", { name: /^How does PgBouncer/ });
  await open.click();
  const thread = page.getByRole("region", { name: "Conversation" });
  await expect(thread.getByRole("article", { name: "Answer" })).toHaveCount(2);
  await expect(open).toHaveAttribute("aria-current", "true");

  // Continue it: it moves to the top with one more question; no new conversation.
  await page.getByRole("textbox", { name: "Ask a follow-up question" }).fill("anything about prepared statements?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(thread.getByRole("article", { name: "Answer" })).toHaveCount(3);
  await expect(entries.first()).toContainText("3 questions");
  await expect(historyTab).toContainText("4");

  // Survives a reload.
  await page.reload();
  await page.getByRole("tab", { name: /History/ }).click();
  await expect(entries.first()).toContainText("How does PgBouncer transaction pooling work?");

  // Delete the open conversation with confirmation: the stage resets.
  await entries.first().getByRole("button", { name: /^How does PgBouncer/ }).click();
  await expect(thread.getByRole("article", { name: "Answer" })).toHaveCount(3);
  await entries.first().hover();
  await entries.first().getByRole("button", { name: /Delete conversation/ }).click();
  await page.getByRole("button", { name: "Delete conversation", exact: true }).click();
  await expect(page.getByRole("tab", { name: /History/ })).toContainText("3");
  await expect(page.getByRole("heading", { name: "What do you want to know?" })).toBeVisible();
});
