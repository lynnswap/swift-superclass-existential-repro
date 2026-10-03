#!/usr/bin/env python3
"""Build portable probes, then run each case in a separate process."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ("LayoutProbe", "CastProbe", "RuntimeProbe")
CONFIGURATIONS = ("debug", "release")
CASES = (
    ("LayoutProbe", "unconstrained", True),
    ("CastProbe", "unconstrained", True),
    ("CastProbe", "protocol-only", True),
    ("CastProbe", "superclass-only", True),
    ("LayoutProbe", "constrained", False),
    ("CastProbe", "constrained", False),
)


def command(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, **kwargs)


def checked(args, **kwargs):
    result = command(args, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{args!r} exited {result.returncode}\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def environment():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "os": checked(["sw_vers"]),
        "architecture": platform.machine(),
        "kernel": platform.release(),
        "runnerImage": os.environ.get("ImageOS"),
        "runnerImageVersion": os.environ.get("ImageVersion"),
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    info = environment()
    info.update(
        compiler=checked(["xcrun", "swiftc", "--version"]),
        xcode=checked(["xcodebuild", "-version"]),
        sdk=checked(["xcrun", "--sdk", "macosx", "--show-sdk-version"]),
        developerDirectory=os.environ.get("DEVELOPER_DIR") or checked(["xcode-select", "-p"]),
        commit=command(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip() or None,
        binaries={},
    )
    save(output / "build.json", info)
    for configuration in CONFIGURATIONS:
        args = ["xcrun", "swift", "build", "--package-path", str(ROOT),
                "--configuration", configuration]
        result = command(args)
        (output / f"build-{configuration}.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Swift build failed; see {output / f'build-{configuration}.log'}")
        directory = Path(checked(args + ["--show-bin-path"]))
        target = output / configuration
        target.mkdir(exist_ok=True)
        for name in PRODUCTS:
            path = target / name
            shutil.copy2(directory / name, path)
            info["binaries"][f"{configuration}/{name}"] = digest(path)
    save(output / "build.json", info)
    print(f"Built Debug and Release probes in {output}")


def execute(path, arguments, log):
    try:
        result = command([str(path), *arguments], timeout=30)
        output = {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired as error:
        output = {"exitCode": None, "stdout": (error.stdout or b"").decode(errors="replace"),
                  "stderr": (error.stderr or b"").decode(errors="replace"), "status": "timeout"}
    log.with_suffix(".stdout.txt").write_text(output["stdout"])
    log.with_suffix(".stderr.txt").write_text(output["stderr"])
    return output


def classify(result, product, mode):
    if result.get("status") == "timeout":
        return
    if result["exitCode"] < 0:
        result["status"] = "crashed"
        return
    if result["exitCode"]:
        result["status"] = "process-failed"
        return
    try:
        value = json.loads(result["stdout"])
        if value["mode"] != mode:
            raise ValueError("The probe returned another mode.")
        if product == "LayoutProbe":
            for layout in (value["concrete"], value["generic"]):
                if not all(isinstance(layout[key], int) for key in ("size", "stride", "alignment")):
                    raise ValueError("Incomplete layout output.")
            result["status"] = "passed" if value["concrete"] == value["generic"] else "layout-mismatch"
        else:
            result["status"] = "passed" if value.get("value") == 42 else "cast-failed"
        result["result"] = value
    except (ValueError, TypeError, KeyError):
        result["status"] = "invalid-output"


def summary(report):
    build_info = report["build"]
    lines = ["# Swift superclass existential reproduction", "",
             f"Outcome: **{report['outcome']}**", "",
             "## Build", "", "```text", build_info["xcode"], build_info["compiler"],
             build_info["os"], "```", "", "## Execution", "", "```text",
             report["host"]["os"], f"Architecture: {report['host']['architecture']}", "```", ""]
    for configuration, runtime in report["runtimes"].items():
        lines.append(f"{configuration}: `" + "`, `".join(runtime["swiftCoreImages"]) + "`")
    lines += ["", "| Configuration | Probe | Case | Status | Result |",
              "| --- | --- | --- | --- | --- |"]
    for case in report["cases"]:
        result = case.get("result", {})
        detail = (f"{result['concrete']['size']} / {result['generic']['size']} bytes"
                  if "concrete" in result else f"exit {case['exitCode']}")
        lines.append(f"| {case['configuration']} | {case['product']} | {case['mode']} | {case['status']} | {detail} |")
    lines += ["", "The build compiler and execution OS are recorded separately.",
              "A crash is an observed process termination; inspect its logs before attributing its cause.", ""]
    return "\n".join(lines)


def run(bundle, output):
    output.mkdir(parents=True, exist_ok=True)
    build_info = json.loads((bundle / "build.json").read_text())
    report = {"build": build_info, "host": environment(), "runtimes": {}, "cases": []}
    # Archive checksums establish that the OS comparison runs identical binaries.
    for name, expected in build_info["binaries"].items():
        if digest(bundle / name) != expected:
            raise RuntimeError(f"Binary checksum mismatch: {name}")
    for configuration in CONFIGURATIONS:
        runtime = execute(bundle / configuration / "RuntimeProbe", [], output / f"{configuration}-runtime")
        if runtime["exitCode"] != 0:
            raise RuntimeError(f"RuntimeProbe did not complete: {runtime}")
        runtime_info = json.loads(runtime["stdout"])
        if not runtime_info["swiftCoreImages"]:
            raise RuntimeError("RuntimeProbe could not identify the loaded Swift core library.")
        report["runtimes"][configuration] = runtime_info
        for product, mode, control in CASES:
            result = execute(bundle / configuration / product, [mode],
                             output / f"{configuration}-{product}-{mode}")
            classify(result, product, mode)
            result.update(configuration=configuration, product=product, mode=mode, control=control)
            report["cases"].append(result)
            print(configuration, product, mode, result["status"], flush=True)
    controls_pass = all(case["status"] == "passed" for case in report["cases"] if case["control"])
    infrastructure_failure = any(case["status"] in {"invalid-output", "process-failed", "timeout"}
                                 for case in report["cases"])
    if not controls_pass or infrastructure_failure:
        report["outcome"] = "inconclusive"
        exit_code = 2
    elif all(case["status"] == "passed" for case in report["cases"]):
        report["outcome"] = "not-reproduced"
        exit_code = 0
    else:
        report["outcome"] = "reproduced"
        exit_code = 1
    save(output / "report.json", report)
    rendered = summary(report)
    (output / "summary.md").write_text(rendered)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a") as stream:
            stream.write(rendered)
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--output", type=Path, required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--bundle", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        (args.output / "infrastructure-error.json").unlink(missing_ok=True)
        if args.action == "build":
            build(args.output.resolve())
            return 0
        return run(args.bundle.resolve(), args.output.resolve())
    except (OSError, ValueError, RuntimeError) as error:
        args.output.mkdir(parents=True, exist_ok=True)
        save(args.output / "infrastructure-error.json", {"outcome": "inconclusive", "error": str(error)})
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
