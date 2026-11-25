import { expect, test } from "@playwright/test";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { once } from "node:events";
import {
  cpSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { createInterface } from "node:readline";

test("the desktop shell opens the bundled shacl-py catalogue", async ({
  page,
}) => {
  const bin = readdirSync("src-tauri/binaries").find((name) =>
    name.startsWith("ds-reader-"),
  )!;
  let viewer: ChildProcessWithoutNullStreams | undefined;
  let exit: Promise<unknown> | undefined;
  const outbound: string[] = [];
  const root = mkdtempSync(resolve(tmpdir(), "ds-view-catalogue-"));
  cpSync("tests/fixtures/catalogue", root, { recursive: true });
  try {
    await page.exposeFunction(
      "desktopIPC",
      async (command: string, args: { initial?: boolean; url?: string }) => {
        if (command === "plugin:opener|open_url") {
          outbound.push(args.url!);
          return;
        }
        if (command !== "open_project")
          throw new Error(`Unknown command ${command}`);
        if (args.initial || viewer) return null;
        viewer = spawn(resolve("src-tauri/binaries", bin), ["--view", root]);
        viewer.stderr.on("data", (part) => process.stderr.write(part));
        exit = once(viewer, "exit");
        const output = createInterface({ input: viewer.stdout });
        for await (const line of output) return JSON.parse(line);
        throw new Error("Viewer exited before opening the fixture");
      },
    );
    await page.addInitScript(() => {
      if (window !== window.top) return;
      Object.assign(window, {
        __TAURI_INTERNALS__: {
          invoke: (cmd: string, args: object) =>
            (
              window as unknown as {
                desktopIPC: (c: string, a: object) => unknown;
              }
            ).desktopIPC(cmd, args),
        },
      });
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Open project folder" }).click();
    const catalogue = page.frameLocator('iframe[title="Project catalogue"]');
    await expect(
      catalogue.getByRole("heading", { name: "Reference list" }),
    ).toBeVisible({ timeout: 60000 });
    await expect(page.getByRole("button", { name: "Refresh" })).toBeEnabled();
    await catalogue.getByRole("link", { name: "Tidal cycles" }).click();
    await expect(catalogue.locator(".refdrawer")).toContainText("Tidal cycles");
    await catalogue
      .locator('.refdrawer a[href="https://example.org/tides"]')
      .click();
    await expect.poll(() => outbound).toEqual(["https://example.org/tides"]);
    await expect(
      catalogue.getByRole("link", { name: "Open in Papers" }),
    ).toHaveCount(0);
    await catalogue.getByRole("link", { name: "Close", exact: true }).click();
    await catalogue
      .locator(".study header")
      .getByRole("link", { name: /Papers/ })
      .click();
    await expect(
      catalogue.getByRole("heading", { name: "Shoreline survey" }),
    ).toBeVisible();
    await expect(
      catalogue.getByRole("heading", { name: "Station readings" }),
    ).toBeVisible();
    await catalogue.getByRole("link", { name: "readings.csv" }).click();
    await expect(catalogue.locator(".drawer")).toContainText("readings.csv");
    await catalogue.getByRole("link", { name: "Close", exact: true }).click();
    await catalogue.getByRole("link", { name: /^Figures/ }).click();
    await expect(catalogue.locator("figcaption")).toContainText(
      "Station comparison",
    );
    const metadata = resolve(root, "metadata.yaml");
    writeFileSync(
      metadata,
      readFileSync(metadata, "utf8").replace(
        "Station comparison",
        "Updated station comparison",
      ),
    );
    await page.getByRole("button", { name: "Refresh" }).click();
    await expect(catalogue.locator("figcaption")).toContainText(
      "Updated station comparison",
      { timeout: 20000 },
    );
    await catalogue
      .getByRole("link", { name: "Raw metadata", exact: true })
      .click();
    await expect(catalogue.locator("article pre").first()).toContainText(
      "dataset_links:",
    );
    await catalogue
      .locator(".study header")
      .getByRole("link", { name: "Graph" })
      .click();
    // The frozen runtime loads the graph component on its first visit.
    const graph = catalogue.getByRole("group", {
      name: "Network of papers, datasets and labels",
    });
    await expect(graph.locator("a.node").first()).toBeVisible({
      timeout: 45000,
    });
    await page.getByRole("button", { name: "Open project folder" }).click(); // cancel
    await expect(
      catalogue.getByRole("heading", { name: "Network graph" }),
    ).toBeVisible();
  } catch (error) {
    const frame = page
      .frames()
      .find((candidate) => candidate !== page.mainFrame());
    if (frame)
      console.error(
        await frame
          .locator("body")
          .innerText({ timeout: 3000 })
          .catch(() => "Viewer disconnected"),
      );
    throw error;
  } finally {
    viewer?.stdin.end();
    await exit;
    rmSync(root, { recursive: true, force: true });
  }
});
