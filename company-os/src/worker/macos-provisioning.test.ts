import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const packageRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);
const provisioner = path.join(
  packageRoot,
  "scripts",
  "provision-macos-worker.mjs",
);

interface RenderedService {
  label: string;
  paths: {
    runnerPath: string;
    stdoutPath: string;
    stderrPath: string;
    plistPath: string;
  };
  runner: string;
  plist: string;
}

function render(): RenderedService {
  const output = execFileSync(
    process.execPath,
    [
      provisioner,
      "render",
      "--repo",
      "/Users/Zach & Team/Followville's Repo",
      "--home",
      "/Users/Zach & Team",
      "--node",
      "/Applications/Node Tools/node",
      "--pnpm",
      "/Applications/Node Tools/pnpm",
      "--provider-name",
      "claude",
      "--provider-path",
      "/Applications/Claude's Tools/claude",
    ],
    { encoding: "utf8" },
  );
  return JSON.parse(output) as RenderedService;
}

test("macOS worker service generation is deterministic", () => {
  assert.deepEqual(render(), render());
});

test("launchd plist is always-on and treats paths as data", () => {
  const rendered = render();
  assert.equal(rendered.label, "com.followville.company-os.worker");
  assert.match(rendered.plist, /<key>RunAtLoad<\/key>\s*<true\/>/u);
  assert.match(rendered.plist, /<key>KeepAlive<\/key>\s*<true\/>/u);
  assert.match(
    rendered.plist,
    /<string>\/Users\/Zach &amp; Team\/Followville&apos;s Repo<\/string>/u,
  );
  assert.match(
    rendered.plist,
    /<string>\/Users\/Zach &amp; Team\/\.followville-company-os\/bin\/run-worker\.zsh<\/string>/u,
  );
  assert.doesNotMatch(rendered.plist, /SUPABASE|SECRET|PRIVATE_KEY/u);
});

test("runner safely quotes paths and starts the watch worker", () => {
  const rendered = render();
  assert.match(
    rendered.runner,
    /export CLAUDE_CODE_PATH='\/Applications\/Claude'"'"'s Tools\/claude'/u,
  );
  assert.match(
    rendered.runner,
    /cd '\/Users\/Zach & Team\/Followville'"'"'s Repo'/u,
  );
  assert.match(
    rendered.runner,
    /exec '\/Applications\/Node Tools\/pnpm' --dir '\/Users\/Zach & Team\/Followville'"'"'s Repo\/apps\/company-dashboard' worker -- --watch/u,
  );
  assert.doesNotMatch(rendered.runner, /SUPABASE_SECRET_KEY=/u);
});
