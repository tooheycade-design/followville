import assert from "node:assert/strict";
import { mkdtemp, mkdir, realpath, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import {
  HeadlessBlenderPreviewRunner,
  type BlenderPreviewCommand,
  type BlenderPreviewCommandRunner,
} from "./blender-preview.js";
import type { Worktree } from "./worktree.js";

async function fixture(): Promise<{
  root: string;
  trustedRoot: string;
  worktree: Worktree;
}> {
  const root = await mkdtemp(path.join(tmpdir(), "blender-preview-"));
  const trustedRoot = path.join(root, "trusted");
  const worktreePath = path.join(root, "task");
  await mkdir(path.join(trustedRoot, "company-os", "scripts"), {
    recursive: true,
  });
  await mkdir(worktreePath);
  await writeFile(
    path.join(trustedRoot, "company-os", "scripts", "blender-preview.py"),
    "# trusted fixture\n",
  );
  return {
    root,
    trustedRoot,
    worktree: { path: worktreePath, branch: "agent/task-test", baseCommit: "a" },
  };
}

test("rejects traversal and unsupported inputs before command discovery", async () => {
  const setup = await fixture();
  const outside = path.join(setup.root, "outside.glb");
  await writeFile(outside, "glb");
  await writeFile(path.join(setup.worktree.path, "notes.txt"), "no");
  let calls = 0;
  const commandRunner: BlenderPreviewCommandRunner = async () => {
    calls += 1;
    return { exitCode: 0, stdout: "Blender 4.5", stderr: "" };
  };
  const runner = new HeadlessBlenderPreviewRunner(setup.trustedRoot, {
    commandRunner,
    environment: {},
  });

  const traversal = await runner.run({
    worktree: setup.worktree,
    inputFile: "../outside.glb",
    runId: "run-1",
    signal: new AbortController().signal,
  });
  const unsupported = await runner.run({
    worktree: setup.worktree,
    inputFile: "notes.txt",
    runId: "run-2",
    signal: new AbortController().signal,
  });

  assert.equal(traversal.passed, false);
  assert.match(traversal.output, /inside the worktree/);
  assert.equal(unsupported.passed, false);
  assert.match(unsupported.output, /\.glb or \.gltf/);
  assert.equal(calls, 0);
});

test("rejects a symlink that resolves outside the worktree", async (t) => {
  const setup = await fixture();
  const outside = path.join(setup.root, "outside.glb");
  const link = path.join(setup.worktree.path, "escaped.glb");
  await writeFile(outside, "glb");
  try {
    await symlink(outside, link, "file");
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "EPERM" || code === "EACCES") {
      t.skip("Symlink creation is not permitted on this machine.");
      return;
    }
    throw error;
  }
  const runner = new HeadlessBlenderPreviewRunner(setup.trustedRoot, {
    commandRunner: async () => {
      throw new Error("command discovery must not run");
    },
    environment: {},
  });

  const result = await runner.run({
    worktree: setup.worktree,
    inputFile: link,
    runId: "run-symlink",
    signal: new AbortController().signal,
  });

  assert.equal(result.passed, false);
  assert.match(result.output, /inside the worktree/);
});

test("discovers Blender safely, scrubs secrets, and parses artifacts", async () => {
  const setup = await fixture();
  const model = path.join(setup.worktree.path, "town's model.glb");
  await writeFile(model, "glb");
  const commands: BlenderPreviewCommand[] = [];
  const commandRunner: BlenderPreviewCommandRunner = async (command) => {
    commands.push(command);
    if (command.args[0] === "--version") {
      return command.executable === "/custom/blender"
        ? { exitCode: 0, stdout: "Blender 4.5.1\n", stderr: "" }
        : { exitCode: 1, stdout: "", stderr: "not found" };
    }
    return {
      exitCode: 0,
      stdout:
        "Blender chatter\nCOMPANY_OS_BLENDER_RESULT=" +
        JSON.stringify({
          passed: true,
          message: "Rendered neutral preview.",
          artifacts: [
            "preview-front.png",
            "preview-side.png",
            "preview-rear.png",
            "technical-report.json",
            "validated.glb",
            "../escape.txt",
          ],
          metrics: { objects: 4, meshes: 2, triangles: 12 },
        }),
      stderr: "",
    };
  };
  const runner = new HeadlessBlenderPreviewRunner(setup.trustedRoot, {
    commandRunner,
    environment: {
      FOLLOWVILLE_BLENDER_PATH: "/custom/blender",
      PATH: "/usr/bin",
      SUPABASE_SERVICE_ROLE_KEY: "secret",
      OPENAI_API_KEY: "secret",
    },
    platform: "linux",
    homeDirectory: "/home/test",
  });

  const result = await runner.run({
    worktree: setup.worktree,
    inputFile: model,
    runId: "run-safe",
    signal: new AbortController().signal,
  });

  assert.equal(result.passed, true);
  assert.match(result.output, /"triangles":12/);
  assert.deepEqual(result.artifactFiles, [
    ".company-os/evidence/run-safe/blender/acd0d3439811/preview-front.png",
    ".company-os/evidence/run-safe/blender/acd0d3439811/preview-side.png",
    ".company-os/evidence/run-safe/blender/acd0d3439811/preview-rear.png",
    ".company-os/evidence/run-safe/blender/acd0d3439811/technical-report.json",
    ".company-os/evidence/run-safe/blender/acd0d3439811/validated.glb",
  ]);
  assert.equal(commands.length, 2);
  const render = commands[1];
  assert.ok(render);
  assert.equal(render.executable, "/custom/blender");
  assert.deepEqual(render.args.slice(0, 5), [
    "--factory-startup",
    "--background",
    "--disable-autoexec",
    "--python",
    path.join(
      setup.trustedRoot,
      "company-os",
      "scripts",
      "blender-preview.py",
    ),
  ]);
  assert.ok(render.args.includes(await realpath(model)));
  assert.equal(render.env["SUPABASE_SERVICE_ROLE_KEY"], undefined);
  assert.equal(render.env["OPENAI_API_KEY"], undefined);
  assert.equal(render.env["PATH"], "/usr/bin");
});

test("checks Blender 5.1 and 5.0 Windows locations before older releases", async () => {
  const setup = await fixture();
  await writeFile(path.join(setup.worktree.path, "scene.glb"), "glb");
  const probes: string[] = [];
  const commandRunner: BlenderPreviewCommandRunner = async (command) => {
    if (command.args[0] === "--version") {
      probes.push(command.executable);
      return command.executable.includes("Blender 5.0")
        ? { exitCode: 0, stdout: "Blender 5.0.0", stderr: "" }
        : { exitCode: 1, stdout: "", stderr: "not installed" };
    }
    return {
      exitCode: 0,
      stdout:
        'COMPANY_OS_BLENDER_RESULT={"passed":true,"artifacts":[]}',
      stderr: "",
    };
  };
  const runner = new HeadlessBlenderPreviewRunner(setup.trustedRoot, {
    commandRunner,
    environment: {},
    platform: "win32",
    homeDirectory: "C:\\Users\\test",
  });

  const result = await runner.run({
    worktree: setup.worktree,
    inputFile: "scene.glb",
    runId: "run-windows",
    signal: new AbortController().signal,
  });

  assert.equal(result.passed, true);
  assert.deepEqual(probes, [
    "C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe",
    "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe",
  ]);
});

test("reports availability without opening an input file", async () => {
  const setup = await fixture();
  const runner = new HeadlessBlenderPreviewRunner(setup.trustedRoot, {
    commandRunner: async (command) =>
      command.executable === "/known/blender"
        ? { exitCode: 0, stdout: "Blender 5.1.0", stderr: "" }
        : { exitCode: 1, stdout: "", stderr: "missing" },
    environment: { FOLLOWVILLE_BLENDER_PATH: "/known/blender" },
    platform: "linux",
  });

  const availability = await runner.checkAvailability({
    worktreePath: setup.worktree.path,
    signal: new AbortController().signal,
  });

  assert.deepEqual(availability, {
    available: true,
    detail: "/known/blender",
  });
});

test("validates external glTF resources before discovering Blender", async () => {
  const setup = await fixture();
  const assets = path.join(setup.worktree.path, "assets");
  await mkdir(assets);
  await writeFile(path.join(assets, "mesh.bin"), "mesh");
  await writeFile(path.join(assets, "texture.png"), "png");
  await writeFile(
    path.join(setup.worktree.path, "valid.gltf"),
    JSON.stringify({
      buffers: [{ uri: "assets/mesh.bin" }],
      images: [
        { uri: "assets/texture.png" },
        { uri: "data:image/png;base64,cG5n" },
      ],
    }),
  );
  await writeFile(
    path.join(setup.worktree.path, "escaped.gltf"),
    JSON.stringify({ buffers: [{ uri: "../outside.bin" }] }),
  );
  await writeFile(path.join(setup.root, "outside.bin"), "outside");
  let probes = 0;
  const commandRunner: BlenderPreviewCommandRunner = async (command) => {
    probes += 1;
    return command.args[0] === "--version"
      ? { exitCode: 0, stdout: "Blender 5.1", stderr: "" }
      : {
          exitCode: 0,
          stdout:
            'COMPANY_OS_BLENDER_RESULT={"passed":true,"artifacts":[]}',
          stderr: "",
        };
  };
  const runner = new HeadlessBlenderPreviewRunner(setup.trustedRoot, {
    commandRunner,
    environment: { FOLLOWVILLE_BLENDER_PATH: "blender" },
  });

  const valid = await runner.run({
    worktree: setup.worktree,
    inputFile: "valid.gltf",
    runId: "run-gltf-valid",
    signal: new AbortController().signal,
  });
  assert.equal(valid.passed, true);
  assert.equal(probes, 2);

  probes = 0;
  const escaped = await runner.run({
    worktree: setup.worktree,
    inputFile: "escaped.gltf",
    runId: "run-gltf-escaped",
    signal: new AbortController().signal,
  });
  assert.equal(escaped.passed, false);
  assert.match(escaped.output, /inside the worktree/);
  assert.equal(probes, 0);
});

test("reports command timeout and malformed subprocess output", async () => {
  const setup = await fixture();
  await writeFile(path.join(setup.worktree.path, "scene.glb"), "glb");
  const runner = new HeadlessBlenderPreviewRunner(setup.trustedRoot, {
    timeoutMs: 1234,
    environment: { FOLLOWVILLE_BLENDER_PATH: "blender" },
    commandRunner: async (command) =>
      command.args[0] === "--version"
        ? { exitCode: 0, stdout: "Blender 4.5", stderr: "" }
        : {
            exitCode: 1,
            stdout: "ordinary output",
            stderr: "render stopped",
            timedOut: true,
          },
  });

  const result = await runner.run({
    worktree: setup.worktree,
    inputFile: "scene.glb",
    runId: "run-timeout",
    signal: new AbortController().signal,
  });

  assert.equal(result.passed, false);
  assert.match(result.output, /timed out after 1234ms/);
  assert.match(result.output, /render stopped/);
  assert.deepEqual(result.artifactFiles, []);
});

test("canonical content preview reads only the trusted town and records provenance", async () => {
  const setup = await fixture();
  const trustedTown = path.join(setup.trustedRoot, "town.glb");
  await writeFile(trustedTown, "canonical town");
  await writeFile(
    path.join(setup.trustedRoot, "world_state.json"),
    JSON.stringify({ day: 27, pop: 500, buildings: [{}, {}] }),
  );
  const commands: BlenderPreviewCommand[] = [];
  const runner = new HeadlessBlenderPreviewRunner(setup.trustedRoot, {
    environment: { FOLLOWVILLE_BLENDER_PATH: "blender" },
    commandRunner: async (command) => {
      commands.push(command);
      if (command.args[0] === "--version") {
        return { exitCode: 0, stdout: "Blender 5.1", stderr: "" };
      }
      const outputIndex = command.args.indexOf("--output");
      assert.notEqual(outputIndex, -1);
      await mkdir(command.args[outputIndex + 1] as string, { recursive: true });
      return {
        exitCode: 0,
        stdout:
          'COMPANY_OS_BLENDER_RESULT={"passed":true,"artifacts":["preview-portrait-town.png"]}',
        stderr: "",
      };
    },
  });

  const result = await runner.run({
    worktree: setup.worktree,
    inputFile: "town.glb",
    runId: "run-canonical",
    signal: new AbortController().signal,
    profile: "canonical-content",
    overlays: ["Every follow built this.", "500 residents"],
    expectedTownState: { day: 27, population: 500, buildingCount: 2 },
  });

  assert.equal(result.passed, true);
  assert.equal(result.artifactFiles.length, 2);
  assert.match(result.artifactFiles[1] ?? "", /source-provenance\.json$/);
  const render = commands.at(-1);
  assert.ok(render);
  assert.ok(render.args.includes(await realpath(trustedTown)));
  assert.deepEqual(
    render.args.slice(render.args.indexOf("--profile")),
    [
      "--profile",
      "canonical-content",
      "--overlay",
      "Every follow built this.",
      "--overlay",
      "500 residents",
    ],
  );

  const refused = await runner.run({
    worktree: setup.worktree,
    inputFile: "another.glb",
    runId: "run-canonical-refused",
    signal: new AbortController().signal,
    profile: "canonical-content",
    expectedTownState: { day: 27, population: 500, buildingCount: 2 },
  });
  assert.equal(refused.passed, false);
  assert.match(refused.output, /only use the trusted town\.glb/);

  const stale = await runner.run({
    worktree: setup.worktree,
    inputFile: "town.glb",
    runId: "run-canonical-stale",
    signal: new AbortController().signal,
    profile: "canonical-content",
    expectedTownState: { day: 28, population: 501, buildingCount: 3 },
  });
  assert.equal(stale.passed, false);
  assert.match(stale.output, /does not match trusted town state/);
});
