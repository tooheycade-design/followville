#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import {
  chmodSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const LABEL = "com.followville.company-os.worker";
const MINIMUM_NODE_MAJOR = 20;
const REQUIRED_ENVIRONMENT = ["SUPABASE_URL", "SUPABASE_SECRET_KEY"];
const SCRIPT_PATH = fileURLToPath(import.meta.url);
const DEFAULT_REPOSITORY = path.resolve(path.dirname(SCRIPT_PATH), "..", "..");

function fail(message) {
  throw new Error(message);
}

function xmlEscape(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function shellQuote(value) {
  return `'${value.replaceAll("'", `'\"'\"'`)}'`;
}

function parseArguments(argv) {
  const [command = "help", ...rest] = argv;
  const options = new Map();
  for (let index = 0; index < rest.length; index += 1) {
    const item = rest[index];
    if (!item?.startsWith("--")) {
      fail(`Unexpected argument: ${item ?? ""}`);
    }
    const value = rest[index + 1];
    if (value === undefined || value.startsWith("--")) {
      fail(`Missing value for ${item}.`);
    }
    options.set(item.slice(2), value);
    index += 1;
  }
  return { command, options };
}

function option(options, name, fallback) {
  return options.get(name) ?? fallback;
}

function assertMacOs() {
  if (process.platform !== "darwin") {
    fail("Installing a launchd worker is supported only on macOS.");
  }
}

function run(executable, args, settings = {}) {
  const result = spawnSync(executable, args, {
    cwd: settings.cwd,
    encoding: "utf8",
    env: settings.env ?? process.env,
    stdio: settings.inherit ? "inherit" : "pipe",
    timeout: settings.timeoutMs ?? 120_000,
  });
  if (result.error) {
    fail(`${settings.description ?? executable} failed: ${result.error.message}`);
  }
  return result;
}

function commandPath(name) {
  const result = run("/usr/bin/which", [name], {
    description: `Locating ${name}`,
  });
  const discovered = result.status === 0 ? result.stdout.trim() : "";
  const candidates = [
    discovered,
    `/opt/homebrew/bin/${name}`,
    `/usr/local/bin/${name}`,
    path.join(os.homedir(), ".local", "bin", name),
    path.join(os.homedir(), ".npm-global", "bin", name),
  ];
  const candidate = candidates.find(
    (value) =>
      value.length > 0 && existsSync(value) && statSync(value).isFile(),
  );
  return candidate === undefined ? null : realpathSync(candidate);
}

function parseEnvironmentFile(contents) {
  const values = new Map();
  for (const rawLine of contents.split(/\r?\n/u)) {
    const line = rawLine.trim();
    if (line.length === 0 || line.startsWith("#")) continue;
    const match = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/u.exec(
      line,
    );
    if (match === null) continue;
    let value = match[2]?.trim() ?? "";
    if (
      value.length >= 2 &&
      ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'")))
    ) {
      value = value.slice(1, -1);
    }
    values.set(match[1], value);
  }
  return values;
}

function validateEnvironmentFile(environmentPath) {
  if (!existsSync(environmentPath)) {
    fail(`Missing ${environmentPath}. Create the dashboard environment file first.`);
  }
  const linkInfo = lstatSync(environmentPath);
  if (linkInfo.isSymbolicLink() || !linkInfo.isFile()) {
    fail(`${environmentPath} must be a regular file, not a symlink.`);
  }
  const info = statSync(environmentPath);
  if (typeof process.getuid === "function" && info.uid !== process.getuid()) {
    fail(`${environmentPath} must be owned by the current user.`);
  }
  if ((info.mode & 0o077) !== 0) {
    fail(
      `${environmentPath} is readable or writable by other users. Run: chmod 600 ${shellQuote(
        environmentPath,
      )}`,
    );
  }
  const values = parseEnvironmentFile(readFileSync(environmentPath, "utf8"));
  const missing = REQUIRED_ENVIRONMENT.filter(
    (name) => (values.get(name) ?? "").trim().length === 0,
  );
  if (missing.length > 0) {
    fail(`${environmentPath} is missing required variable(s): ${missing.join(", ")}.`);
  }
  return values;
}

function validateRepository(repository) {
  const resolved = realpathSync(repository);
  for (const required of [
    "package.json",
    "pnpm-lock.yaml",
    path.join("apps", "company-dashboard", "package.json"),
    path.join("apps", "company-dashboard", "src", "worker", "main.ts"),
  ]) {
    if (!existsSync(path.join(resolved, required))) {
      fail(`${resolved} is not a complete Followville repository (${required} missing).`);
    }
  }
  return resolved;
}

function validateNode(nodePath) {
  const result = run(nodePath, ["--version"], { description: "Node.js validation" });
  if (result.status !== 0) fail("Node.js could not report its version.");
  const match = /^v(\d+)\./u.exec(result.stdout.trim());
  if (match === null || Number(match[1]) < MINIMUM_NODE_MAJOR) {
    fail(
      `Node.js ${MINIMUM_NODE_MAJOR} or newer is required; found ${
        result.stdout.trim() || "an unknown version"
      }.`,
    );
  }
  return result.stdout.trim();
}

function expectedPnpmVersion(repository) {
  const packageJson = JSON.parse(readFileSync(path.join(repository, "package.json"), "utf8"));
  const specification = packageJson.packageManager;
  const match = /^pnpm@(.+)$/u.exec(
    typeof specification === "string" ? specification : "",
  );
  if (match === null) {
    fail("The repository does not pin a pnpm version in package.json.");
  }
  return match[1];
}

function validatePnpm(pnpmPath, expectedVersion) {
  const result = run(pnpmPath, ["--version"], { description: "pnpm validation" });
  if (result.status !== 0) fail("pnpm could not report its version.");
  const actualVersion = result.stdout.trim();
  if (actualVersion !== expectedVersion) {
    fail(`pnpm ${expectedVersion} is required; found ${actualVersion || "unknown"}.`);
  }
  return actualVersion;
}

function executableFromEnvironment(values, name) {
  const configured = values.get(name);
  if (configured === undefined || configured.trim().length === 0) return null;
  const candidate = path.resolve(configured.trim());
  if (!existsSync(candidate) || !statSync(candidate).isFile()) {
    fail(`${name} points to a missing executable: ${candidate}`);
  }
  return realpathSync(candidate);
}

function findProviders(values) {
  const providers = [];
  const codex =
    executableFromEnvironment(values, "CODEX_CLI_PATH") ?? commandPath("codex");
  if (codex !== null) providers.push({ name: "codex", path: codex });
  const claude =
    executableFromEnvironment(values, "CLAUDE_CODE_PATH") ?? commandPath("claude");
  if (claude !== null) providers.push({ name: "claude", path: claude });
  if (providers.length === 0) {
    fail(
      "No provider CLI found. Install and sign in to Codex or Claude Code, or set CODEX_CLI_PATH/CLAUDE_CODE_PATH in .env.local.",
    );
  }
  return providers;
}

function pathApiFor(targetPath) {
  return targetPath.startsWith("/") ? path.posix : path;
}

function supportPaths(home) {
  const pathApi = pathApiFor(home);
  const supportRoot = pathApi.join(home, ".followville-company-os");
  return {
    supportRoot,
    runnerPath: pathApi.join(supportRoot, "bin", "run-worker.zsh"),
    stdoutPath: pathApi.join(supportRoot, "logs", "worker.log"),
    stderrPath: pathApi.join(supportRoot, "logs", "worker.error.log"),
    plistPath: pathApi.join(
      home,
      "Library",
      "LaunchAgents",
      `${LABEL}.plist`,
    ),
  };
}

function providerEnvironmentLines(providers) {
  return providers.map(({ name, path: providerPath }) => {
    const variable = name === "codex" ? "CODEX_CLI_PATH" : "CLAUDE_CODE_PATH";
    return `export ${variable}=${shellQuote(providerPath)}`;
  });
}

function generateRunner({ repository, nodePath, pnpmPath, providers }) {
  const pathApi = pathApiFor(repository);
  const dashboard = pathApi.join(repository, "apps", "company-dashboard");
  const executableDirectories = [
    pathApi.dirname(nodePath),
    pathApi.dirname(pnpmPath),
    ...providers.map((provider) => pathApi.dirname(provider.path)),
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
  ];
  const uniquePath = [...new Set(executableDirectories)].join(":");
  return [
    "#!/bin/zsh",
    "set -eu",
    "umask 077",
    `export PATH=${shellQuote(uniquePath)}`,
    ...providerEnvironmentLines(providers),
    `cd ${shellQuote(repository)}`,
    `exec ${shellQuote(pnpmPath)} --dir ${shellQuote(
      dashboard,
    )} worker -- --watch`,
    "",
  ].join("\n");
}

function generatePlist({ repository, runnerPath, stdoutPath, stderrPath }) {
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
    '<plist version="1.0">',
    "<dict>",
    "  <key>Label</key>",
    `  <string>${xmlEscape(LABEL)}</string>`,
    "  <key>ProgramArguments</key>",
    "  <array>",
    "    <string>/bin/zsh</string>",
    `    <string>${xmlEscape(runnerPath)}</string>`,
    "  </array>",
    "  <key>WorkingDirectory</key>",
    `  <string>${xmlEscape(repository)}</string>`,
    "  <key>RunAtLoad</key>",
    "  <true/>",
    "  <key>KeepAlive</key>",
    "  <true/>",
    "  <key>ProcessType</key>",
    "  <string>Background</string>",
    "  <key>ThrottleInterval</key>",
    "  <integer>15</integer>",
    "  <key>StandardOutPath</key>",
    `  <string>${xmlEscape(stdoutPath)}</string>`,
    "  <key>StandardErrorPath</key>",
    `  <string>${xmlEscape(stderrPath)}</string>`,
    "</dict>",
    "</plist>",
    "",
  ].join("\n");
}

function atomicWrite(filePath, contents, mode) {
  mkdirSync(path.dirname(filePath), { recursive: true, mode: 0o700 });
  const temporary = `${filePath}.tmp-${process.pid}`;
  writeFileSync(temporary, contents, { encoding: "utf8", mode });
  chmodSync(temporary, mode);
  renameSync(temporary, filePath);
}

function ensurePrivateLog(filePath) {
  mkdirSync(path.dirname(filePath), { recursive: true, mode: 0o700 });
  writeFileSync(filePath, "", { encoding: "utf8", flag: "a", mode: 0o600 });
  chmodSync(filePath, 0o600);
}

function providerEnvironment(providers) {
  const environment = { ...process.env };
  for (const provider of providers) {
    if (provider.name === "codex") environment.CODEX_CLI_PATH = provider.path;
    if (provider.name === "claude") environment.CLAUDE_CODE_PATH = provider.path;
  }
  return environment;
}

function runWorkerCheck(repository, pnpmPath, providers) {
  const dashboard = path.join(repository, "apps", "company-dashboard");
  const result = run(pnpmPath, ["--dir", dashboard, "worker", "--", "--check"], {
    cwd: repository,
    description: "Company OS worker readiness check",
    env: providerEnvironment(providers),
    timeoutMs: 180_000,
  });
  const output = `${result.stdout}${result.stderr}`;
  process.stdout.write(output);
  if (result.status !== 0) {
    fail(`Worker readiness check exited with status ${result.status}.`);
  }
  if (!/provider [^:\r\n]+: ready\b/iu.test(output)) {
    fail(
      "Worker readiness check did not confirm a signed-in provider. Sign in to Codex or Claude Code and retry.",
    );
  }
}

function launchDomain() {
  if (typeof process.getuid !== "function") fail("Unable to determine the user ID.");
  return `gui/${process.getuid()}`;
}

function install(options) {
  assertMacOs();
  const repository = validateRepository(
    option(options, "repo", DEFAULT_REPOSITORY),
  );
  const home = path.resolve(option(options, "home", os.homedir()));
  const environmentPath = path.join(
    repository,
    "apps",
    "company-dashboard",
    ".env.local",
  );
  const values = validateEnvironmentFile(environmentPath);
  const nodePath = realpathSync(option(options, "node", process.execPath));
  const nodeVersion = validateNode(nodePath);
  const pnpmPath = realpathSync(
    option(options, "pnpm", commandPath("pnpm") ?? fail("pnpm was not found in PATH.")),
  );
  const pnpmVersion = validatePnpm(
    pnpmPath,
    expectedPnpmVersion(repository),
  );
  const providers = findProviders(values);

  console.log(
    `Preflight: ${nodeVersion}, pnpm ${pnpmVersion}, provider(s) ${providers
      .map((provider) => provider.name)
      .join(", ")}.`,
  );
  runWorkerCheck(repository, pnpmPath, providers);

  const paths = supportPaths(home);
  const runner = generateRunner({ repository, nodePath, pnpmPath, providers });
  const plist = generatePlist({ repository, ...paths });
  atomicWrite(paths.runnerPath, runner, 0o700);
  atomicWrite(paths.plistPath, plist, 0o600);
  ensurePrivateLog(paths.stdoutPath);
  ensurePrivateLog(paths.stderrPath);

  const domain = launchDomain();
  run("/bin/launchctl", ["bootout", domain, paths.plistPath], {
    description: "Stopping an existing Company OS worker",
  });
  const bootstrap = run("/bin/launchctl", ["bootstrap", domain, paths.plistPath], {
    description: "Installing the Company OS worker",
  });
  if (bootstrap.status !== 0) {
    fail(`launchctl bootstrap failed: ${bootstrap.stderr.trim()}`);
  }
  const kickstart = run("/bin/launchctl", ["kickstart", "-k", `${domain}/${LABEL}`], {
    description: "Starting the Company OS worker",
  });
  if (kickstart.status !== 0) {
    fail(`launchctl kickstart failed: ${kickstart.stderr.trim()}`);
  }
  const loaded = run("/bin/launchctl", ["print", `${domain}/${LABEL}`], {
    description: "Verifying the Company OS worker",
  });
  if (loaded.status !== 0) {
    fail(`The worker was installed but launchd did not keep it loaded: ${loaded.stderr.trim()}`);
  }
  console.log(`Installed and started ${LABEL}.`);
  console.log(`Status: ${shellQuote(nodePath)} ${shellQuote(SCRIPT_PATH)} status`);
  console.log(`Logs: ${paths.stdoutPath}`);
}

function status(options) {
  assertMacOs();
  const home = path.resolve(option(options, "home", os.homedir()));
  const paths = supportPaths(home);
  const domain = launchDomain();
  const result = run("/bin/launchctl", ["print", `${domain}/${LABEL}`], {
    description: "Reading Company OS worker status",
  });
  console.log(`LaunchAgent: ${existsSync(paths.plistPath) ? "installed" : "not installed"}`);
  console.log(`Service: ${result.status === 0 ? "loaded" : "not loaded"}`);
  console.log(`Output log: ${paths.stdoutPath}`);
  console.log(`Error log: ${paths.stderrPath}`);
  if (result.status === 0) process.stdout.write(result.stdout);
  else process.exitCode = 1;
}

function uninstall(options) {
  assertMacOs();
  const home = path.resolve(option(options, "home", os.homedir()));
  const paths = supportPaths(home);
  const domain = launchDomain();
  run("/bin/launchctl", ["bootout", domain, paths.plistPath], {
    description: "Stopping the Company OS worker",
  });
  rmSync(paths.plistPath, { force: true });
  rmSync(paths.runnerPath, { force: true });
  console.log(`Uninstalled ${LABEL}. Logs were preserved at ${path.dirname(paths.stdoutPath)}.`);
}

function render(options) {
  const repository = option(options, "repo", "/Users/zach/Followville Repo");
  const home = option(options, "home", "/Users/zach");
  const nodePath = option(options, "node", "/opt/homebrew/bin/node");
  const pnpmPath = option(options, "pnpm", "/opt/homebrew/bin/pnpm");
  const providerName = option(options, "provider-name", "codex");
  if (providerName !== "codex" && providerName !== "claude") {
    fail("--provider-name must be codex or claude.");
  }
  const providers = [
    {
      name: providerName,
      path: option(
        options,
        "provider-path",
        `/opt/homebrew/bin/${providerName}`,
      ),
    },
  ];
  const paths = supportPaths(home);
  process.stdout.write(
    JSON.stringify({
      label: LABEL,
      paths,
      runner: generateRunner({ repository, nodePath, pnpmPath, providers }),
      plist: generatePlist({ repository, ...paths }),
    }),
  );
}

function usage() {
  console.log(`Followville Company OS macOS worker

Usage:
  node company-os/scripts/provision-macos-worker.mjs install [--repo PATH]
  node company-os/scripts/provision-macos-worker.mjs status
  node company-os/scripts/provision-macos-worker.mjs uninstall

Install performs the complete preflight, runs worker --check, and only then
installs an always-on per-user LaunchAgent. Credentials remain exclusively in
apps/company-dashboard/.env.local.`);
}

try {
  const { command, options } = parseArguments(process.argv.slice(2));
  if (command === "install") install(options);
  else if (command === "status") status(options);
  else if (command === "uninstall") uninstall(options);
  else if (command === "render") render(options);
  else if (command === "help" || command === "--help") usage();
  else fail(`Unknown command: ${command}`);
} catch (error) {
  console.error(`Error: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
