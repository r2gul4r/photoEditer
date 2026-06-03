#!/usr/bin/env node
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = resolve(import.meta.dirname, "..");
const command = process.argv[2] ?? "help";
const rest = process.argv.slice(3);
const isWindows = process.platform === "win32";

function resolveCommandPath(commandName) {
  if (!isWindows) return commandName;
  const appDataCommand = process.env.APPDATA ? join(process.env.APPDATA, "npm", commandName) : null;
  if (appDataCommand && existsSync(appDataCommand)) return appDataCommand;
  const localAppDataCommand = process.env.LOCALAPPDATA ? join(process.env.LOCALAPPDATA, "pnpm", commandName) : null;
  if (localAppDataCommand && existsSync(localAppDataCommand)) return localAppDataCommand;
  const result = spawnSync("where.exe", [commandName], {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.status !== 0) return null;
  return result.stdout.trim().split(/\r?\n/)[0] ?? null;
}

function cmdQuote(value) {
  return `"${String(value).replace(/"/g, '""')}"`;
}

function spawnCommand(commandName, args, options = {}) {
  if (isWindows && /\.(cmd|bat)$/i.test(commandName)) {
    const line = [commandName, ...args].map(cmdQuote).join(" ");
    return spawnSync(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", line], {
      cwd: options.cwd ?? root,
      env: process.env,
      encoding: options.capture ? "utf8" : undefined,
      stdio: options.capture ? ["ignore", "pipe", "pipe"] : "inherit",
      windowsVerbatimArguments: true,
    });
  }

  return spawnSync(commandName, args, {
    cwd: options.cwd ?? root,
    env: process.env,
    encoding: options.capture ? "utf8" : undefined,
    stdio: options.capture ? ["ignore", "pipe", "pipe"] : "inherit",
  });
}

function pnpmRunnerFromPath(commandPath) {
  if (isWindows && /\.cmd$/i.test(commandPath)) {
    const pnpmCli = join(dirname(commandPath), "node_modules", "pnpm", "bin", "pnpm.cjs");
    if (existsSync(pnpmCli)) return { command: process.execPath, prefixArgs: [pnpmCli] };
  }
  return { command: commandPath, prefixArgs: [] };
}

function npxRunnerFromPath(commandPath) {
  if (isWindows && /\.cmd$/i.test(commandPath)) {
    const npxCli = join(dirname(commandPath), "node_modules", "npm", "bin", "npx-cli.js");
    if (existsSync(npxCli)) return { command: process.execPath, prefixArgs: [npxCli] };
  }
  return { command: commandPath, prefixArgs: [] };
}

function runnerWorks(runner, args = ["--version"]) {
  const result = spawnCommand(runner.command, [...runner.prefixArgs, ...args], { capture: true });
  return result.status === 0;
}

function resolvePnpm() {
  const pnpmNames = isWindows ? ["pnpm.cmd", "pnpm"] : ["pnpm"];
  for (const name of pnpmNames) {
    const commandPath = resolveCommandPath(name);
    if (!commandPath) continue;
    const runner = pnpmRunnerFromPath(commandPath);
    if (runnerWorks(runner)) return runner;
  }

  const npx = isWindows ? "npx.cmd" : "npx";
  const npxPath = resolveCommandPath(npx);
  if (npxPath) {
    const runner = npxRunnerFromPath(npxPath);
    if (runnerWorks(runner)) return { command: runner.command, prefixArgs: [...runner.prefixArgs, "--yes", "pnpm@10.14.0"] };
  }

  console.error("pnpm or npx was not found. Install Node.js 20+, then retry.");
  process.exit(1);
}

function run(commandName, args, options = {}) {
  const result = spawnCommand(commandName, args, options);
  if (result.signal) {
    console.error(`Command stopped by signal ${result.signal}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function runPnpm(args) {
  const pnpm = resolvePnpm();
  run(pnpm.command, [...pnpm.prefixArgs, ...args]);
}

function runNodeScript(scriptPath, args = []) {
  run(process.execPath, [join(root, scriptPath), ...args]);
}

function ensureNodeDeps() {
  if (!existsSync(join(root, "node_modules"))) {
    console.log("[photo] installing workspace dependencies...");
    runPnpm(["install"]);
  }
}

function ensureBackend() {
  console.log("[photo] checking backend environment...");
  runNodeScript("scripts/setup.mjs");
}

function printHelp() {
  console.log(`TonePilot Local CLI

Usage:
  photo install      Install frontend and backend dependencies
  photo dev          Install/check dependencies, then start the local web app
  photo setup        Install/check backend dependencies
  photo doctor       Print setup status
  photo backend      Start backend only
  photo desktop      Start frontend only
  photo test         Run backend tests and frontend build

One-time registration from the cloned repository:
  npm link
`);
}

switch (command) {
  case "install":
    console.log("[photo] installing workspace dependencies...");
    runPnpm(["install"]);
    runNodeScript("scripts/setup.mjs", rest);
    break;
  case "dev":
  case "start":
    ensureNodeDeps();
    ensureBackend();
    runPnpm(["dev", ...rest]);
    break;
  case "setup":
    ensureNodeDeps();
    runNodeScript("scripts/setup.mjs", rest);
    break;
  case "doctor":
    runNodeScript("scripts/setup.mjs", ["--check", ...rest]);
    break;
  case "backend":
    ensureNodeDeps();
    ensureBackend();
    runPnpm(["backend:dev", ...rest]);
    break;
  case "desktop":
    ensureNodeDeps();
    runPnpm(["desktop:dev", ...rest]);
    break;
  case "test":
    ensureNodeDeps();
    runPnpm(["backend:test"]);
    runPnpm(["desktop:build"]);
    break;
  case "build":
    ensureNodeDeps();
    runPnpm(["desktop:build", ...rest]);
    break;
  case "help":
  case "--help":
  case "-h":
    printHelp();
    break;
  default:
    console.error(`Unknown command: ${command}`);
    printHelp();
    process.exit(1);
}
