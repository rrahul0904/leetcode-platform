const { expect, test } = require("@playwright/test");

const harnessUrl =
  "http://localhost:3001/sign-in/browser-test/guided-practice";
const storageKey = "skillsforge.guided-practice:browser-guided-practice";

async function expectActiveStage(page, index, label) {
  await expect(
    page.getByRole("tab", { name: new RegExp(`${index}\\. ${label}`, "i") }),
  ).toHaveAttribute("aria-selected", "true");
}

test("completes the guided flow and restores browser-local progress", async ({ page }, testInfo) => {
  await page.goto(harnessUrl);

  await expect(
    page.getByRole("region", { name: "Guided practice journey" }),
  ).toBeVisible();
  await expect(page.getByText("0 of 5 stages signed off")).toBeVisible();
  await expectActiveStage(page, 1, "Study");
  await expect(
    page.getByText("Choose a reliable aggregation strategy."),
  ).toBeVisible();

  const complete = page.getByRole("button", { name: "Mark this step complete" });
  await complete.click();
  await expect(page.getByText("1 of 5 stages signed off")).toBeVisible();
  await expectActiveStage(page, 2, "Discover");
  await expect(page.getByText("Handle duplicate events safely.")).toBeVisible();

  await complete.click();
  await expect(page.getByText("2 of 5 stages signed off")).toBeVisible();
  await expectActiveStage(page, 3, "Practice");
  await expect(complete).toBeDisabled();

  const reflection =
    "I preserve one aggregation invariant and process each event once, so time is linear.";
  await page
    .getByLabelText("Explain your planned approach and complexity in your own words.")
    .fill(reflection);
  await expect(complete).toBeEnabled();
  await complete.click();

  await expect(page.getByText("3 of 5 stages signed off")).toBeVisible();
  await expectActiveStage(page, 4, "Create");
  await expect(
    page.getByText(/Run and Submit remain governed by the existing secure execution/i),
  ).toBeVisible();
  await complete.click();

  await expect(page.getByText("4 of 5 stages signed off")).toBeVisible();
  await expectActiveStage(page, 5, "Challenge");
  await expect(
    page.getByText(/Name one assumption you would revisit and one trade-off/i),
  ).toBeVisible();
  await complete.click();
  await expect(page.getByText("5 of 5 stages signed off")).toBeVisible();

  await page.reload();
  await expect(page.getByText("5 of 5 stages signed off")).toBeVisible();
  await expectActiveStage(page, 5, "Challenge");

  const restored = await page.evaluate((key) => {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  }, storageKey);
  expect(restored).toMatchObject({
    activeStage: "challenge",
    completed: ["study", "discover", "practice", "create", "challenge"],
    reflection,
    focusMode: false,
  });

  const timerValue = page.getByLabel("Practice timer").locator("strong");
  await expect(timerValue).toBeVisible();
  await page.getByRole("button", { name: "Hide timer" }).click();
  await expect(page.getByRole("button", { name: "Show timer" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(timerValue).toBeHidden();
  await expect(page.getByTestId("workspace-sentinel")).toBeVisible();
  await expect(page.getByTestId("tutor-sentinel")).toBeVisible();

  await expect
    .poll(async () =>
      page.evaluate((key) => {
        const raw = window.localStorage.getItem(key);
        return raw ? JSON.parse(raw).focusMode : null;
      }, storageKey),
    )
    .toBe(true);

  await page.reload();
  await expect(page.getByRole("button", { name: "Show timer" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByLabel("Practice timer").locator("strong")).toBeHidden();

  await page.screenshot({
    fullPage: true,
    path: testInfo.outputPath("guided-practice-desktop.png"),
  });
});

test("keeps all five learning stages usable on a narrow viewport", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(harnessUrl);

  const tablist = page.getByRole("tablist", { name: "Learning stages" });
  await expect(tablist).toBeVisible();

  for (const [index, label] of [
    [1, "Study"],
    [2, "Discover"],
    [3, "Practice"],
    [4, "Create"],
    [5, "Challenge"],
  ]) {
    await expect(
      page.getByRole("tab", { name: new RegExp(`${index}\\. ${label}`, "i") }),
    ).toBeVisible();
  }

  const overflow = await tablist.evaluate(
    (element) => element.scrollWidth > element.clientWidth + 1,
  );
  expect(overflow).toBe(false);

  await expect(page.getByRole("button", { name: "Hide timer" })).toBeVisible();
  await page.screenshot({
    fullPage: true,
    path: testInfo.outputPath("guided-practice-mobile.png"),
  });
});
