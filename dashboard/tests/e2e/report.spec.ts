import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SECTIONS = ["how-many", "call-plan", "alignment", "limits", "quality", "method"];
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const running = (page: Page) => page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length);
const mapReady = async (page: Page) => expect(page.locator("#map svg path.county").first()).toBeAttached({ timeout: 15_000 });
const violations = async (page: Page) =>
  (await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map(
    (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`,
  );

test.describe("the report", () => {
  test("loads with its title, one h1 and the six sections", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto("/");
    await mapReady(page);
    await expect(page).toHaveTitle(/Field Force Planner/);
    await expect(page.locator("h1")).toHaveCount(1);
    for (const id of SECTIONS) await expect(page.locator(`#${id}`)).toHaveCount(1);
    await expect(page.getByRole("navigation", { name: "Sections" })).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("the headline gives both headcounts and the first screen draws the county map", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("about 1,310 reps");
    await expect(page.locator("h1")).toContainText("about 474");
    await mapReady(page);
    expect(await page.locator("#map svg path.county").count()).toBe(3142);
    await expect(page.locator("#map svg path.cut")).toHaveCount(1);
    await expect(page.locator("#map svg path.hatch")).toHaveCount(1);
    await expect(page.locator(".key")).toContainText("865 counties are cut between territories");
  });

  test("switching franchise redraws the map and its heading", async ({ page }) => {
    await page.goto("/");
    await mapReady(page);
    await expect(page.locator("#map h3")).toContainText("1,310 diabetes territories");
    await page.locator("#map .seg button", { hasText: "Oncology" }).click();
    await expect(page.locator("#map h3")).toContainText("474 oncology territories");
    await expect(page.locator(".key")).toContainText("343 counties are cut between territories");
  });

  test("the oncology cut lines are fetched only when oncology is chosen", async ({ page }) => {
    const fetched: string[] = [];
    page.on("request", (r) => r.url().includes("cut-oncology") && fetched.push(r.url()));
    await page.goto("/");
    await mapReady(page);
    await expect(page.locator("#map svg path.cut")).toHaveAttribute("d", /^M/);
    expect(fetched).toEqual([]);
    await page.locator("#map .seg button", { hasText: "Oncology" }).click();
    await expect(page.locator("#map h3")).toContainText("474 oncology territories");
    await expect.poll(() => fetched.length).toBe(1);
    await expect(page.locator("#map svg path.cut")).toHaveAttribute("d", /^M/);
    await page.locator("#map .seg button", { hasText: "Diabetes" }).click();
    await page.locator("#map .seg button", { hasText: "Oncology" }).click();
    expect(fetched).toHaveLength(1); // fetched once, kept
  });

  test("the state zoom changes the view and a county can be read in words", async ({ page }) => {
    await page.goto("/");
    await mapReady(page);
    const before = await page.locator("#map svg").first().getAttribute("viewBox");
    await page.locator("#zoom").selectOption({ label: "Texas" });
    await expect(page.locator("#map svg").first()).not.toHaveAttribute("viewBox", before ?? "");
    const county = page.locator("#map svg path.county").nth(1500);
    await county.dispatchEvent("pointerdown", { bubbles: true });
    await expect(page.locator("#map .readout")).toContainText(/Weight|Cut into/);
  });

  test("every Chart and Table switch works", async ({ page }) => {
    await page.goto("/");
    await mapReady(page);
    const figures = page.locator("figure.fig:has(.seg button:text-is('Table'))");
    const n = await figures.count();
    expect(n).toBeGreaterThanOrEqual(3);
    for (let i = 0; i < n; i++) {
      const fig = figures.nth(i);
      await fig.scrollIntoViewIfNeeded();
      await fig.getByRole("button", { name: "Table", exact: true }).click();
      await expect(fig.locator("table.tbl").first()).toBeVisible();
      await fig.getByRole("button", { name: "Chart", exact: true }).click();
    }
  });

  test("the map's table lists territories 25 a page and filters by state", async ({ page }) => {
    await page.goto("/");
    await page.locator("#map").getByRole("button", { name: "Table", exact: true }).click();
    await expect(page.locator("#map tbody tr")).toHaveCount(25);
    await page.locator("#tstate").selectOption({ label: "Wyoming" });
    expect(await page.locator("#map tbody tr").count()).toBeLessThan(25);
    await expect(page.locator("#map tbody tr").first()).toContainText("WY");
  });

  test("the rulers draw one tick per rep, and the state ledger opens to all 51 states", async ({ page }) => {
    await page.goto("/");
    const rulers = page.locator("#how-many svg[role=img]").first();
    expect(await rulers.locator("line.tk").count()).toBe(1310);
    await expect(page.locator("#how-many")).toContainText("36.3% of diabetes reps are in five states");
    await page.getByRole("button", { name: "Show all 51 states" }).click();
    await expect(page.locator("#how-many figure.fig svg[role=img] text.t-strong").filter({ hasText: "Wyoming" })).toHaveCount(1);
  });

  test("changing a yellow cell changes the headcount, and reset restores the stated plan", async ({ page }) => {
    await page.goto("/");
    const line = page.locator("#call-plan .scenario");
    await expect(line).toContainText("This is the stated plan");
    await page.getByLabel("Calls a rep makes a day").fill("16");
    await expect(line).toContainText("Your scenario needs 655 reps");
    await expect(line).toContainText("The stated plan needs 1,310");
    await page.getByRole("button", { name: "Reset to the stated plan" }).click();
    await expect(line).toContainText("This is the stated plan");
    await expect(line).toContainText("1,310 reps");
  });

  test("the live ruler follows the scenario", async ({ page }) => {
    await page.goto("/");
    const ruler = page.locator("#call-plan svg[role=img]").first();
    await expect(ruler.locator("line.tk")).toHaveCount(1310);
    await page.getByLabel("Field days a year").fill("95");
    await expect(ruler.locator("line.tk")).toHaveCount(2620);
  });

  test("the balance charts show both cuts, and the profile can be read by rank", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#alignment h2")).toContainText("99.6%");
    await expect(page.locator("#alignment h2")).toContainText("8.8%");
    const first = page.locator("#alignment figure.fig svg[role=img]").first();
    await first.locator("rect[fill=transparent]").hover({ position: { x: 60, y: 60 } });
    await expect(page.locator("#alignment .readout").first()).toContainText(/Rank [\d,]+ of 1,310\. Weight/);
  });

  test("the limits section reports the reality check as found", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#limits")).toContainText("0.86");
    await expect(page.locator("#limits")).toContainText("−0.10");
  });

  test("the scorecard lists every check with its status in words", async ({ page }) => {
    await page.goto("/");
    expect(await page.locator("#quality .qrow").count()).toBeGreaterThanOrEqual(20);
    await expect(page.locator("#quality .qrow .st", { hasText: "Pass" }).first()).toBeVisible();
  });

  test("the Excel model downloads", async ({ request, page }) => {
    await page.goto("/");
    await expect(page.locator('a[download][href$=".xlsx"]').first()).toBeVisible();
    const res = await request.get("/downloads/Field-Force-Sizing-Model.xlsx");
    expect(res.status()).toBe(200);
    expect((await res.body()).length).toBeGreaterThan(20_000);
  });

  test("theme choice is applied and remembered", async ({ page }) => {
    await page.goto("/");
    await page.locator("button.theme").click();
    const first = await page.locator("html").getAttribute("data-theme");
    expect(["light", "dark"]).toContain(first);
    expect(await page.evaluate(() => localStorage.getItem("ff-theme"))).toBe(first);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", first!);
  });

  test("the share image, icon and map shapes exist", async ({ request }) => {
    expect((await request.get("/opengraph-image.png")).status()).toBe(200);
    expect((await request.get("/icon.svg")).status()).toBe(200);
    expect((await request.get("/data/map.json")).status()).toBe(200);
  });

  test("an unknown address shows the not-found page", async ({ page }) => {
    const res = await page.goto("/nothing-here");
    expect(res?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: "That page does not exist" })).toBeVisible();
  });
});

test.describe("accessibility", () => {
  for (const scheme of ["light", "dark"] as const) {
    test(`axe finds no violations on the desktop page (${scheme})`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/");
      await mapReady(page);
      expect(await violations(page)).toEqual([]);
    });
    test(`axe finds no violations on a phone (${scheme})`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/");
      await mapReady(page);
      expect(await violations(page)).toEqual([]);
    });
  }

  test("with every table open there are still no violations", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    for (const group of await page.locator(".seg:has(button:text-is('Table'))").all()) await group.getByRole("button", { name: "Table", exact: true }).click();
    expect(await violations(page)).toEqual([]);
  });
});

test.describe("phone", () => {
  for (const width of [390, 360, 320]) {
    test.describe(`${width} px wide`, () => {
      test.use({ viewport: { width, height: 800 } });
      test("no sideways scroll, with the charts and then with every table open", async ({ page }) => {
        await page.goto("/");
        await mapReady(page);
        const wide = () => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(await wide()).toBeLessThanOrEqual(1);
        for (const group of await page.locator(".seg:has(button:text-is('Table'))").all()) await group.getByRole("button", { name: "Table", exact: true }).click();
        expect(await wide()).toBeLessThanOrEqual(1);
      });
    });
  }
  test.describe("menu", () => {
    test.use({ viewport: { width: 390, height: 844 } });
    test("the section menu opens and goes to a section", async ({ page }) => {
      await page.goto("/");
      await page.locator(".sections-menu summary").click();
      await page.locator(".sections-menu .menu a", { hasText: "Alignment" }).click();
      await expect(page).toHaveURL(/#alignment$/);
    });
  });
});

test.describe("motion", () => {
  test("with reduced motion nothing is animating after a change", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Calls a rep makes a day").fill("4");
    await page.waitForTimeout(300);
    expect(await running(page)).toBe(0);
  });
  test.describe("with motion allowed", () => {
    test.use({ reducedMotion: "no-preference" });
    test("nothing animates on load, the ruler's new ticks land when the plan changes, and it stops", async ({ page }) => {
      await page.goto("/");
      await page.waitForTimeout(400);
      expect(await running(page)).toBe(0);
      await page.getByLabel("Calls a rep makes a day").fill("4");
      await page.waitForTimeout(100);
      expect(await running(page)).toBeGreaterThan(0);
      await page.waitForTimeout(1200);
      expect(await running(page)).toBe(0);
    });
  });
});
