# Swift superclass existential reproduction

This project checks whether a superclass-constrained existential has the same
layout in concrete and generic code, and whether an ordinary conditional cast
to that type succeeds. It has no ABIBridge dependency and uses no unsafe API in
the reproductions.

The affected type has this form:

```swift
class Base<Value: Hashable> {}
protocol Source<Element>: AnyObject { associatedtype Element }
typealias Value = any Base<Int> & Source<Int>
```

On macOS 26.6.2, the concrete size was 16 bytes while generic code reported
24 bytes. A separate `as?` reproduction terminated inside the Swift runtime.
The observations and investigation are tracked in
[ABIBridge #302](https://github.com/lynnswap/ABIBridge/issues/302).

## Run locally

Requires macOS 15 or later, Python 3.9 or later, and a Swift 6.3 or newer Xcode
toolchain. The package contains command-line probes rather than an app or test
host, so the same executables can run unchanged on another macOS version.

```sh
DEVELOPER_DIR=/Applications/Xcode_26.6.app/Contents/Developer \
  python3 scripts/probes.py build --output .artifacts/probes

python3 scripts/probes.py run \
  --bundle .artifacts/probes \
  --output .artifacts/results
```

Build uses both Debug and Release configurations. Run starts a separate process
for each probe, so a crashing cast does not prevent the controls or the other
configuration from running. To compare another compiler, change `DEVELOPER_DIR`
and use a different build-output directory.

| Probe | Expected behavior |
| --- | --- |
| Constrained layout | Concrete and generic size, stride, and alignment agree |
| Unconstrained layout control | The same measurements agree after removing `Hashable` |
| Constrained cast | Casting `Any` to `any Base<Int> & Source<Int>` returns a value containing `42` |
| Cast controls | Removing `Hashable`, or casting only to the protocol or superclass, returns `42` |

`report.json` records each exit status, output, result, the build compiler, the
execution OS/build, and the Swift core library actually loaded by the process.
`summary.md` is the readable comparison. Binary SHA-256 values establish that
different OS jobs used identical executable files.

The runner exits with:

- **0 — not reproduced:** all probes and controls passed.
- **1 — reproduced:** controls passed, but a constrained probe had a layout
  mismatch, unsuccessful cast, or crashed. A crash records the observed process
  termination; its cause still requires examination.
- **2 — inconclusive:** a control failed, a tool/build failed, output was
  unavailable or invalid, or a process timed out.

These outcomes describe the tested environment. A successful run on one runtime
does not establish that other OS versions are fixed.

## GitHub Actions comparison

The workflow builds one Debug/Release bundle using Xcode 26.6 and another using
Xcode 27.2. It runs these three comparisons:

| Build | Execute | Purpose |
| --- | --- | --- |
| Xcode 26.6 on macOS 26 | macOS 26 | Baseline |
| The same Xcode 26.6 binaries | macOS 27 | Change the OS runtime while holding the compiler output fixed |
| Xcode 27.2 on macOS 27 | macOS 27 | Test the newer compiler and runtime together |

The `macos-26` and `xcode-27` labels both provide arm64 machines. The latter is
GitHub's macOS 27 preview image. Runner versions change over time, so the report
records the actual OS, image, Xcode, and Swift versions for each run. See the
[official runner images](https://github.com/actions/runner-images#available-images)
and [Xcode 27 image](https://github.com/actions/runner-images/blob/main/images/macos/xcode-27-arm64-Readme.md).

**A red reproduction job is expected while the bug remains.** Reports and probe
logs are uploaded even when the probes fail; the workflow does not turn a
reproduced failure into a passing check. Build/setup failures are reported
separately. Each run can be started from the **Actions** tab with
**Compare Swift runtimes → Run workflow**.

## Minimal upstream reproductions

The two files in `Reproducers/` can be submitted independently of the package
and reporting scripts:

```sh
xcrun swiftc -swift-version 6 -Onone Reproducers/Layout.swift -o /tmp/layout-probe
/tmp/layout-probe

xcrun swiftc -swift-version 6 -Onone Reproducers/Cast.swift -o /tmp/cast-probe
/tmp/cast-probe
```

For the layout case, both printed values should agree. For the cast case,
the expected output is `42`. Replace `-Onone` with `-O` to compare optimization.
