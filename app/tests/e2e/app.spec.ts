import { expect, type Page, test } from "@playwright/test";

const READY = /3\.14 ready/;

async function open(page: Page) {
  await page.goto("/");
  await expect(page.locator(".status")).toHaveText(READY, { timeout: 60_000 });
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

test("an exercise: fail, get taught, fix, pass, and keep the draft", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Exercises" }).click();
  await expect(page.locator(".exercise-list button")).toHaveCount(18);
  await page.getByRole("button", { name: "Fix the adding machine" }).click();
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

for (const mode of ["Playground", "Exercises"]) {
  test(`fits a phone screen without sideways scrolling (${mode})`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await open(page);
    await page.getByRole("button", { name: mode }).click();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}
