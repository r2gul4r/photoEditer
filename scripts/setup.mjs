import { existsSync, rmSync, writeFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = resolve(import.meta.dirname, "..");
const backendRoot = join(root, "apps", "backend");
const venvDir = join(backendRoot, ".venv");
const isWindows = process.platform === "win32";
const venvPythonRel = isWindows ? join("Scripts", "python.exe") : join("bin", "python");
const venvPython = join(venvDir, venvPythonRel);
const knownVenvPythons = [".venv", ".venv312", ".venv311"].map((name) => join(backendRoot, name, venvPythonRel));
const noRawMarker = join(venvDir, ".tonepilot-no-raw");
const checkOnly = process.argv.includes("--check");
const noRaw = process.argv.includes("--no-raw");
const retryRaw = process.argv.includes("--retry-raw");

function candidate(command, prefixArgs = [], label = command) {
  return { command, prefixArgs, label };
}

const pythonCandidates = [
  process.env.TONEPILOT_PYTHON ? candidate(process.env.TONEPILOT_PYTHON, [], "TONEPILOT_PYTHON") : null,
  candidate("py", ["-3.12"], "py -3.12"),
  candidate("py", ["-3.11"], "py -3.11"),
  candidate("python3.12", [], "python3.12"),
  candidate("python3.11", [], "python3.11"),
  candidate("python3", [], "python3"),
  candidate("python", [], "python"),
  candidate("py", ["-3"], "py -3"),
].filter(Boolean);

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? root,
    env: process.env,
    encoding: "utf8",
    stdio: options.capture ? ["ignore", "pipe", "pipe"] : "inherit",
  });
  return result;
}

function pythonInfo(item) {
  if ((item.command.includes("\\") || item.command.includes("/")) && !existsSync(item.command)) return null;
  const script = [
    "import sys",
    "print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')",
    "print(sys.executable)",
  ].join("; ");
  const result = run(item.command, [...item.prefixArgs, "-c", script], { capture: true });
  if (result.status !== 0) return null;
  const [version, executable] = result.stdout.trim().split(/\r?\n/);
  const [major, minor] = version.split(".").map((value) => Number.parseInt(value, 10));
  return { ...item, version, executable, major, minor };
}

function resolvePython() {
  const found = pythonCandidates.map(pythonInfo).find((item) => item && item.major === 3 && item.minor >= 11);
  if (!found) {
    console.error("Python 3.11 or newer is required.");
    console.error("Recommended for RAW support: Python 3.11 or 3.12.");
    process.exit(1);
  }
  if (found.minor >= 13) {
    console.warn(`[setup] Python ${found.version} found. Python 3.11 or 3.12 is safer for RAW dependency wheels.`);
  }
  return found;
}

function venvReady() {
  return existsSync(venvPython);
}

function canImport(python, moduleName) {
  const result = run(python, ["-c", `import ${moduleName}`], { capture: true });
  return result.status === 0;
}

function activeVenvPython() {
  return knownVenvPythons.find((path) => existsSync(path) && canImport(path, "fastapi") && canImport(path, "uvicorn")) ?? null;
}

function checkImport(moduleName) {
  const python = activeVenvPython();
  if (!python) return false;
  return canImport(python, moduleName);
}

function targetVenvHasBackendDeps() {
  if (!venvReady()) return false;
  const required = ["fastapi", "uvicorn", "pytest", "exifread"];
  const requiredReady = required.every((moduleName) => canImport(venvPython, moduleName));
  const rawReady = noRaw || canImport(venvPython, "rawpy") || (!retryRaw && existsSync(noRawMarker));
  return requiredReady && rawReady;
}

async function createVenv(python) {
  await mkdir(backendRoot, { recursive: true });
  console.log(`[setup] creating backend venv: ${venvDir}`);
  const result = run(python.command, [...python.prefixArgs, "-m", "venv", venvDir]);
  if (result.status !== 0) {
    console.error("[setup] failed to create Python virtual environment.");
    process.exit(result.status ?? 1);
  }
}

function installBackend(extraSet) {
  const spec = `${backendRoot}[${extraSet}]`;
  console.log(`[setup] installing backend dependencies: ${spec}`);
  return run(venvPython, ["-m", "pip", "install", "-e", spec]);
}

function printCheck() {
  const activePython = activeVenvPython();
  console.log("[setup] status");
  console.log(`  setup target venv: ${venvReady() ? venvDir : "missing"}`);
  console.log(`  active backend python: ${activePython ?? "missing"}`);
  console.log(`  fastapi: ${checkImport("fastapi") ? "ok" : "missing"}`);
  console.log(`  uvicorn: ${checkImport("uvicorn") ? "ok" : "missing"}`);
  console.log(`  pytest: ${checkImport("pytest") ? "ok" : "missing"}`);
  console.log(`  rawpy: ${checkImport("rawpy") ? "ok" : "missing optional"}`);
  console.log(`  exifread: ${checkImport("exifread") ? "ok" : "missing optional"}`);
}

async function main() {
  if (checkOnly) {
    printCheck();
    return;
  }

  if (!venvReady()) {
    await createVenv(resolvePython());
  } else if (targetVenvHasBackendDeps()) {
    console.log(`[setup] backend venv already ready: ${venvDir}`);
    printCheck();
    return;
  } else {
    console.log(`[setup] using existing backend venv: ${venvDir}`);
  }

  const extras = noRaw ? "dev,exif" : "dev,raw,exif";
  const result = installBackend(extras);
  if (result.status !== 0 && !noRaw) {
    console.warn("[setup] RAW dependency install failed. Retrying without rawpy so the app can still run.");
    const fallback = installBackend("dev,exif");
    if (fallback.status !== 0) process.exit(fallback.status ?? 1);
    writeFileSync(noRawMarker, "rawpy install failed; run `pnpm setup -- --retry-raw` to try again.\n");
  } else if (result.status !== 0) {
    process.exit(result.status ?? 1);
  } else if (existsSync(noRawMarker)) {
    rmSync(noRawMarker);
  }

  printCheck();
  console.log("[setup] done. Start the app with: pnpm dev");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
