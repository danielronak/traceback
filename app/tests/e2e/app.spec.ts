import { expect, type Page, test } from "@playwright/test";

const READY = /3\.14 ready/;

async function start(page: Page) {
  await page.goto("/");
  await expect(page.locator(".status")).toHaveText(READY, { timeout: 60_000 });
}

/** Most tests use the playground, which starts with the design doc's mockup. */
async function open(page: Page) {
  await start(page);
  await page.getByRole("button", { name: "Playground" }).click();
}

async function setCode(page: Page, code: string) {
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.press("Delete");
  await page.keyboard.insertText(code);
}

const run = (page: Page) => page.getByRole("button", { name: "Run", exact: true }).click();
const answerBox = (page: Page) => page.getByLabel("Your program is waiting for input:");

test("the design doc's mockup: red on line 2, blue on line 4, then teach and fix", async ({ page }) => {
  await open(page);
  const titles = page.locator(".card-title");
  await expect(titles).toHaveText(["Missing colon on line 2", "Variable names are written in snake_case: total"]);
  await expect(page.locator(".pm-mark-syntax")).toHaveCount(1);
  await expect(page.locator(".pm-mark-style")).toHaveCount(1);
  await expect(page.locator(".pm-tint-syntax")).toHaveCount(1);

  // Try first: the fix stays hidden until asked for.
  await expect(page.locator(".fix")).toHaveCount(0);
  await page.getByRole("button", { name: "Give me a hint" }).click();
  await expect(page.locator(".hints li")).toHaveText(["Look at the very end of line 2."]);
  await page.getByRole("button", { name: "Why does Python work this way?" }).click();
  await expect(page.locator(".why")).toContainText("groups code by indentation");
  await page.getByRole("button", { name: "Show the fix" }).click();
  await expect(page.locator(".fix-after")).toHaveText("if len(scores) > 2:");
  await page.getByRole("button", { name: "Accept fix" }).click();
  await expect(titles).toHaveText(["Variable names are written in snake_case: total"]);
});

test("Run shows the prompt before input() waits, then the program's output", async ({ page }) => {
  await open(page);
  await setCode(page, 'name = input("Name? ")\nprint("Hello, " + name + "!")\n');
  await run(page);
  await expect(answerBox(page)).toBeFocused();
  await expect(page.locator(".console-log")).toHaveText("Name? ");
  await answerBox(page).fill("Ada");
  await page.keyboard.press("Enter");
  await expect(page.locator(".console-log")).toHaveText("Name? Ada\nHello, Ada!\nThe program finished.");
});

test("a crash gets an orange card with the cause, not just Python's message", async ({ page }) => {
  await open(page);
  await setCode(page, 'age = input("Age? ")\nprint(age + 1)\n');
  await run(page);
  await answerBox(page).fill("14");
  await page.keyboard.press("Enter");
  await expect(page.locator(".card-title").first()).toHaveText("age holds text from input(), not a number");
  await expect(page.locator(".pm-tint-runtime")).toHaveCount(1);
});

test("an infinite loop is stopped and explained", async ({ page }) => {
  await open(page);
  await setCode(page, "count = 0\nwhile count < 5:\n    print(count)\n");
  await run(page);
  await expect(page.locator(".card-title").first()).toHaveText(
    "The while loop on line 2 never ends: count never changes",
    { timeout: 30_000 },
  );
});

test("Stop ends a program waiting for input, and a busy one", async ({ page }) => {
  await open(page);
  await setCode(page, "x = input()\nprint('never')\n");
  await run(page);
  await expect(answerBox(page)).toBeVisible();
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.locator(".console-note")).toHaveText("Stopped.");

  await setCode(page, "import time\nwhile True:\n    time.sleep(0.01)\n");
  await run(page);
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible();
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.locator(".console-note")).toHaveText("Stopped.", { timeout: 5_000 });
});

test("the course: overview, a lesson with runnable snippets, then its exercise", async ({ page }) => {
  await start(page);
  await expect(page.locator(".overview-progress")).toContainText("0 of 27 done");
  await page.getByRole("button", { name: "Start: Showing things on screen" }).click();
  await expect(page.locator("#lesson-title")).toHaveText("Showing things on screen");

  const first = page.locator(".snippet").first();
  await first.getByRole("button", { name: "Run" }).click();
  await expect(first.locator(".console-log")).toHaveText("Hello, world!\nI am learning Python.\nThe program finished.");

  // A deliberate mistake gets the card the lesson says it will.
  const broken = page.locator(".snippet.broken").first();
  await broken.getByRole("button", { name: "Run" }).click();
  await expect(broken.locator(".card-title").first()).toHaveText('Did you mean the text "hello"?');

  await page.getByRole("button", { name: "Next: Hello, world!" }).click();
  await setCode(page, 'print("Hello, world!")\n');
  await page.getByRole("button", { name: "Run tests" }).click();
  await expect(page.getByText("All tests pass. Well done!")).toBeVisible();
  await expect(page.locator(".course-item .mark.done")).toHaveCount(2);

  // Progress is kept on this device.
  await page.reload();
  await expect(page.locator(".status")).toHaveText(READY, { timeout: 60_000 });
  await expect(page.locator(".course-item .mark.done")).toHaveCount(2);
  await page.getByRole("button", { name: "Overview" }).click();
  await expect(page.locator(".overview-progress")).toContainText("2 of 27 done");
  await expect(page.getByRole("button", { name: "Continue: Remembering things: variables and input" })).toBeVisible();
});

test("repeating a mistake turns the card into a quick quiz first", async ({ page }) => {
  await open(page);
  // Make the mistake, fix it, and make it again, three times. (Re-running the
  // same broken code counts once: it's still the same mistake.)
  for (let time = 1; time <= 3; time++) {
    if (time > 1) {
      await setCode(page, "x = 1\nif x > 0:\n    print(x)\n");
      await run(page);
      await expect(page.locator(".console-note")).toHaveText("The program finished.");
    }
    await setCode(page, "x = 1\nif x > 0\n    print(x)\n");
    await run(page);
    await expect(page.locator(".card-title").first()).toHaveText("Missing colon on line 2");
    await expect(page.locator(".console-note")).toHaveText("Python couldn't run this. See the card.");
  }
  const card = page.locator(".card").first();
  await expect(card.locator(".quiz-intro")).toBeVisible();
  await expect(card.getByRole("button", { name: "Show the fix" })).toHaveCount(0);
  await card.getByRole("button", { name: "if score > 50", exact: true }).click(); // wrong
  await expect(card.locator(".quiz-feedback")).toHaveText("Not quite. Have another go.");
  await card.getByRole("button", { name: "if score > 50:", exact: true }).click();
  await expect(card.locator(".quiz-right")).toContainText("Right!");
  await expect(card.getByRole("button", { name: "Show the fix" })).toBeVisible();
});

test("feedback stays on the device until downloaded, without code unless chosen", async ({ page }) => {
  await open(page);
  await setCode(page, "x = 1\nraise RuntimeError('boom')\n");
  await run(page);
  await expect(page.locator(".card-title").first()).toHaveText("RuntimeError: boom");

  await setCode(page, "count = 0\nprint(10 / count)\n");
  await run(page);
  const card = page.locator(".card").first();
  await card.getByText("Report a problem with this explanation").click();
  await card.getByLabel("It's confusing").check();
  await card.getByLabel("Anything to add? (optional)").fill("I don't know what 'divide by' means");
  await card.getByRole("button", { name: "Save report" }).click();
  await expect(card.locator(".report-sent")).toContainText("saved on this device");

  await page.getByRole("button", { name: "Settings" }).click();
  const dialog = page.getByRole("dialog", { name: "Settings" });
  await expect(dialog).toContainText("errors it has no lesson for yet (1)");
  await expect(dialog).toContainText("explanations you reported (1)");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    dialog.getByRole("button", { name: "Download feedback" }).click(),
  ]);
  const text = await (await download.createReadStream()).toArray().then((chunks) => Buffer.concat(chunks).toString());
  const data = JSON.parse(text);
  expect(data.unknownErrors[0]).toMatchObject({ code: "RuntimeError", message: "boom", count: 1 });
  expect(data.explanationReports[0]).toMatchObject({ cardId: "zero-division", reason: "confusing" });
  expect(text).not.toContain("raise RuntimeError");
  expect(text).not.toContain("count = 0");
});

test("the teacher setting shows fixes straight away", async ({ page }) => {
  await open(page);
  await expect(page.locator(".fix")).toHaveCount(0);
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByLabel("Show the fix straight away, instead of hints first").check();
  await page.getByRole("button", { name: "Done" }).click();
  await expect(page.locator(".fix-after").first()).toHaveText("if len(scores) > 2:");
});

test("an exercise: fail, get taught, fix, pass, and keep the draft", async ({ page }) => {
  await start(page);
  await page.getByRole("navigation", { name: "Course" }).getByRole("button", { name: /Fix the adding machine/ }).click();
  await page.getByRole("button", { name: "Run tests" }).click();
  await expect(page.locator(".test-fail")).toHaveCount(2);
  await expect(page.locator(".test").first()).toContainText('(got "34")');
  await expect(page.locator(".card-title").first()).toHaveText("The numbers were joined like text instead of added");
  await page.getByRole("button", { name: "Show the fix" }).click();
  await page.getByRole("button", { name: "Accept fix" }).click();
  await page.getByRole("button", { name: "Run tests" }).click();
  await expect(page.getByText("All tests pass. Well done!")).toBeVisible();

  await page.reload();
  await expect(page.locator(".status")).toHaveText(READY, { timeout: 60_000 });
  await expect(page.locator(".exercise h2")).toHaveText("Fix the adding machine");
  await expect(page.locator(".cm-content")).toContainText("a = int(input(");
});

test("works offline after one visit", async ({ page, context }) => {
  await open(page);
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
    if (!navigator.serviceWorker.controller) {
      await new Promise((resolve) => navigator.serviceWorker.addEventListener("controllerchange", resolve, { once: true }));
    }
  });
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator(".status")).toHaveText(READY, { timeout: 60_000 });
  expect(await page.evaluate(() => crossOriginIsolated)).toBe(true);
  await expect(page.locator(".card-title").first()).toHaveText("Missing colon on line 2");
  await setCode(page, "print(input('? ') * 2)\n");
  await run(page);
  await answerBox(page).fill("ab");
  await page.keyboard.press("Enter");
  await expect(page.locator(".console-log")).toHaveText("? ab\nabab\nThe program finished.");
});

for (const mode of ["Playground", "Course"]) {
  test(`fits a phone screen without sideways scrolling (${mode})`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await start(page);
    await page.getByRole("button", { name: mode, exact: true }).click();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}
