const ALLOWED = new Set([
  "APPDATA",
  "CLAUDE_CONFIG_DIR",
  "CODEX_HOME",
  "COLORTERM",
  "COMSPEC",
  "HOME",
  "LANG",
  "LC_ALL",
  "LOCALAPPDATA",
  "NO_COLOR",
  "PATH",
  "PATHEXT",
  "PROGRAMDATA",
  "PROGRAMFILES",
  "PROGRAMFILES(X86)",
  "SYSTEMDRIVE",
  "SYSTEMROOT",
  "TEMP",
  "TERM",
  "TMP",
  "USERDOMAIN",
  "USERNAME",
  "USERPROFILE",
  "WINDIR",
]);

/**
 * Environment visible to an untrusted model CLI.
 *
 * The worker host needs database and GitHub credentials, but the model it
 * invokes does not. Child processes inherit everything unless an explicit
 * environment is supplied, which would otherwise hand those credentials to
 * shell commands the model can run inside its worktree.
 */
export function providerEnvironment(
  source: NodeJS.ProcessEnv = process.env,
): NodeJS.ProcessEnv {
  const result: NodeJS.ProcessEnv = {
    NODE_ENV: source["NODE_ENV"] ?? "production",
  };
  for (const [key, value] of Object.entries(source)) {
    if (value !== undefined && ALLOWED.has(key.toUpperCase())) {
      result[key] = value;
    }
  }
  result["GIT_TERMINAL_PROMPT"] = "0";
  return result;
}
