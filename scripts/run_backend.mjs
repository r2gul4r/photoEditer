import { existsSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";

const root = resolve(import.meta.dirname, "..");
const backendRoot = join(root, "apps", "backend");
const mode = process.argv[2] ?? "dev";
const isWindows = process.platform === "win32";
const venvPythonRel = isWindows ? join("Scripts", "python.exe") : join("bin", "python");

function candidate(command, prefixArgs = [], label = command) {
  return { command, prefixArgs, label };
}

function venvPython(venvName) {
  return join(backendRoot, venvName, venvPythonRel);
}

const candidates = [
  process.env.TONEPILOT_PYTHON ? candidate(process.env.TONEPILOT_PYTHON, [], "TONEPILOT_PYTHON") : null,
  process.env.VIRTUAL_ENV ? candidate(join(process.env.VIRTUAL_ENV, venvPythonRel), [], "VIRTUAL_ENV") : null,
  candidate(venvPython(".venv")),
  candidate(venvPython(".venv312")),
  candidate(venvPython(".venv311")),
  candidate("C:\\tmp\\photoediter-venv311\\Scripts\\python.exe"),
  candidate("C:\\tmp\\photoediter-venv311-20260603\\Scripts\\python.exe"),
  candidate("C:\\tmp\\photoediter-venv314-20260603\\Scripts\\python.exe"),
  candidate("C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python314\\python.exe"),
  candidate("py", ["-3.11"], "py -3.11"),
  candidate("py", ["-3"], "py -3"),
  candidate("python", [], "python"),
].filter(Boolean);

function canUse(candidate) {
  if ((candidate.command.includes("\\") || candidate.command.includes("/")) && !existsSync(candidate.command)) {
    return false;
  }
  const requiredImports = mode === "test" ? ["fastapi", "numpy", "PIL", "pytest"] : ["fastapi", "numpy", "PIL", "uvicorn"];
  const importChecks = requiredImports.map((moduleName) => `import ${moduleName}`).join("; ");
  const result = spawnSync(candidate.command, [...candidate.prefixArgs, "-c", `import sys; ${importChecks}; print(sys.version)`], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return result.status === 0;
}

function resolvePython() {
  const found = candidates.find(canUse);
  if (!found) {
    const tried = candidates.map((item) => `  - ${item.label}`).join("\n");
    console.error(`No usable Python runtime with backend dependencies found.\nTried:\n${tried}`);
    console.error("Run `pnpm setup`, or set TONEPILOT_PYTHON to a prepared venv python.exe, then retry.");
    process.exit(1);
  }
  console.log(`[backend] using Python: ${found.label}`);
  return found;
}

const python = resolvePython();

function commandWorks(command) {
  const result = spawnSync(command, ["--version"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return result.status === 0;
}

function findWindowsCodex() {
  const localAppData = process.env.LOCALAPPDATA;
  if (!localAppData) return null;
  const binRoot = join(localAppData, "OpenAI", "Codex", "bin");
  if (!existsSync(binRoot)) return null;
  const candidates = readdirSync(binRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => join(binRoot, entry.name, "codex.exe"))
    .filter((path) => existsSync(path))
    .map((path) => ({ path, mtimeMs: statSync(path).mtimeMs }))
    .sort((a, b) => b.mtimeMs - a.mtimeMs);
  return candidates[0]?.path ?? null;
}

function resolveCodexCommand() {
  if (process.env.TONEPILOT_CODEX_COMMAND) return process.env.TONEPILOT_CODEX_COMMAND;
  if (commandWorks("codex")) return "codex";
  if (process.platform === "win32") return findWindowsCodex();
  return null;
}

const childEnv = { ...process.env };
const codexCommand = resolveCodexCommand();
if (!childEnv.TONEPILOT_CODEX_COMMAND && codexCommand) {
  childEnv.TONEPILOT_CODEX_COMMAND = codexCommand;
  console.log(`[backend] using Codex command: ${codexCommand}`);
} else if (!codexCommand) {
  console.warn("[backend] Codex command not found. AI mode will fall back to local rules unless configured.");
}

const commands = {
  dev: {
    cwd: backendRoot,
    args: ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8765"],
  },
  test: {
    cwd: root,
    args: ["-m", "pytest", "apps/backend/tests"],
  },
  "smoke:codex-status": {
    cwd: root,
    args: ["scripts/smoke_codex_recommend.py"],
  },
  "smoke:codex": {
    cwd: root,
    args: ["scripts/smoke_codex_recommend.py", "--allow-codex-model-call"],
  },
};

const command = commands[mode];
if (!command) {
  console.error(`Unknown backend mode: ${mode}`);
  console.error(`Expected one of: ${Object.keys(commands).join(", ")}`);
  process.exit(1);
}

const child = spawn(python.command, [...python.prefixArgs, ...command.args], {
  cwd: command.cwd,
  env: childEnv,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    console.error(`[backend] exited from signal ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 0);
});
