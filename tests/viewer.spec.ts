import { expect, test } from "@playwright/test";
import { spawn } from "node:child_process";
import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import { createInterface } from "node:readline";

test("the same catalogue layout and navigation on both engines", async ({
  page,
}, testInfo) => {
  const bin = readdirSync("src-tauri/binaries").find((name) =>
    name.startsWith("ds-reader-"),
  )!;
  const proc = spawn(resolve("src-tauri/binaries", bin), [], {
    stdio: ["pipe", "pipe", "inherit"],
  });
  const replies: ((value: string) => void)[] = [];
  createInterface({ input: proc.stdout }).on("line", (line) =>
    replies.shift()?.(line),
  );
  try {
    await page.exposeFunction(
      "catalogueIPC",
      async (command: string, args: { initial?: boolean; query?: object }) => {
        if (command === "open_project" && args.initial) return null;
        const msg =
          command === "open_project"
            ? { op: "open", root: resolve("tests/fixtures/catalogue") }
            : args.query;
        const line = new Promise<string>((resolve) => replies.push(resolve));
        proc.stdin.write(JSON.stringify(msg) + "\n");
        const reply = JSON.parse(await line);
        if (reply.error) throw new Error(reply.error);
        return reply.value;
      },
    );
    await page.addInitScript(() => {
      Object.assign(window, {
        __TAURI_INTERNALS__: {
          invoke: (cmd: string, args: object) =>
            (
              window as unknown as {
                catalogueIPC: (c: string, a: object) => unknown;
              }
            ).catalogueIPC(cmd, args),
        },
      });
      Object.assign(window, { documentIdentity: Math.random() });
    });
    await page.goto("/");
    const identity = await page.evaluate("window.documentIdentity");
    await page.getByRole("button", { name: "Open project folder" }).click();
    await expect(
      page.getByRole("heading", { name: "Shoreline survey" }),
    ).toBeVisible({ timeout: 45000 });
    await expect(
      page.getByRole("heading", { name: "Station readings" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "readings.csv" }),
    ).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const layout = await page.evaluate(() => ({
      side: document.querySelector(".sidebar")!.getBoundingClientRect().right,
      main: document.querySelector("main.detail")!.getBoundingClientRect().left,
      font: document.fonts.check('600 28px "Source Serif 4"'),
      overflow: document.documentElement.scrollWidth > window.innerWidth,
    }));
    expect(layout).toEqual({
      side: 280,
      main: 280,
      font: true,
      overflow: false,
    });
    await testInfo.attach("catalogue", {
      body: await page.screenshot(),
      contentType: "image/png",
    });
    await page.getByRole("button", { name: /Station means/ }).click();
    await page.getByRole("button", { name: "means.csv" }).click();
    await page.getByRole("button", { name: "Preview text" }).click();
    await expect(page.locator("pre")).toContainText("station,mean");
    await page.getByRole("button", { name: "Notes", exact: true }).click();
    await expect(page.getByText("Compare the two stations.")).toBeVisible();
    await page
      .getByRole("button", { name: "Raw metadata", exact: true })
      .click();
    await expect(page.locator(".source pre").first()).toContainText(
      "dataset_links:",
    );
    await page
      .getByRole("searchbox", { name: "Search catalogue" })
      .fill("readings.csv");
    await expect(
      page.getByRole("button", { name: /Second survey/ }),
    ).toBeVisible();
    expect(await page.evaluate("window.documentIdentity")).toEqual(identity);
  } finally {
    proc.stdin.end();
  }
});
