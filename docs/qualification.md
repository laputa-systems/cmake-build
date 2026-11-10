# Qualification

## Published native qualification

The [native qualification run](https://github.com/laputa-systems/cmake-build/actions/runs/42900481859)
qualified the exact archives at commit `5932be3` on x86-64 and ARM64 runners.
Both passed the ELF audit, basic, network, parity, and real-project suites,
as well as size and five-run memory gates. The upstream subset results are
listed below.

| Target | Archive bytes | Archive SHA-256 | Detached results |
| --- | ---: | --- | --- |
| x86-64 musl | 8,125,188 | `cbab9ea823b0e1b609b7b3b273e6a9a8c89d3bfdb7aa382d380f880bf7f78e7c` | [x86-64 results](https://github.com/laputa-systems/cmake-build/releases/download/cmake-4.4.5-5932be3ecbc4-run42907504620-1/results-x86_64-unknown-linux-musl.json) |
| ARM64 musl | 7,571,476 | `66ec96c09705c67adfa83494bf512dc4b7eb5f6cb0f9d706d8499bb460a1c3a8` | [ARM64 results](https://github.com/laputa-systems/cmake-build/releases/download/cmake-4.4.5-5932be3ecbc4-run42907504620-1/results-aarch64-unknown-linux-musl.json) |

The x86-64 archive matched two independent clean builds. ARM64 clean-build
reproduction was not run.

## x86-64 ELF audit

The production build is a static PIE with a non-executable stack, RELRO, and immediate binding. The audit checks the target machine, runtime dependencies, symbol versions, compiler markers, host paths, and OpenSSL library and API references. A probe link identifies archive members before the final link. The audit checks those members and rejects the final output if its selected members differ.

The audit allows CMake and libarchive version-recognition identifiers and `openssl-probe` certificate-discovery identifiers. It rejects other OpenSSL text. The binary contains no OpenSSL library or API symbols under these checks.

## Preliminary x86-64 parity

The graph and archive fixtures passed on the staged CMake 4.4.5 binary and Kitware's official 4.4.5 binary. The candidate ran in the locked Alpine builder. The reference ran in Debian trixie-slim at image index `sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`. Both used the pinned LLVM toolchain on the same native x86-64 host.

The graph fixture exercised Ninja and Unix Makefiles, compiler checks, generated files, transitive and imported targets, module and config packages, installation, downstream consumption, incremental builds, presets, file API replies, and selected system-information fields. The archive fixture created and extracted gzip, xz, bzip2, zstd, and zip archives through both `cmake -E tar` and `file()`.

The selected system-information fields matched. The Ninja build files differed in the `edit_cache` command: the reference distribution includes `ccmake`, and the staged distribution does not. The file API cache replies also differed in these fields:

- The reference included `CMAKE_EDIT_COMMAND` for `ccmake`.
- `CMAKE_INSTALL_SO_NO_EXE` was `1` in Debian and `0` in Alpine. The bundled Linux platform module selects that default from `/etc/debian_version`.
- The Makefiles generator selected `/usr/bin/make` in Debian and `/usr/bin/gmake` in Alpine.
- The detected `uname` path was `/usr/bin/uname` in Debian and `/bin/uname` in Alpine.

The Ninja codemodel listed the `base` and `wrapper` dependencies in the opposite order, and the target reply filename differed. A later run matched that ordering, so it varies between runs. Both generated executables and the downstream executable ran successfully. The effect of the dependency ordering on other consumers has not been established.

The registered parity suite covers the fixtures above.

## x86-64 networking

The staged CMake passed local HTTPS downloads, redirects, expected hash checks, certificate-file and certificate-directory trust, hostname rejection, verification settings, and an HTTP CONNECT proxy. The negative cases returned the expected TLS status or hash mismatch.

A separate networked container used `FetchContent` to download the locked CMake source archive and verify its SHA-256. The local tests ran with only loopback networking. The registered network qualification command passed.

## x86-64 real-project results

fmt 12.2.1 initially passed 18 of 21 CTest cases. `chrono-test`, `unicode-test`, and `xchar-test` failed locale assertions. An official CMake build with the same toolchain reproduced all three failures. Musl accepts a locale name even when locale data is absent, but fmt's test helper interpreted the accepted name as evidence that data existed. A test-only helper correction uses fmt's existing missing-locale path when `MUSL_LOCPATH` is unset. With that correction, all 21 CTest cases passed. Locale-specific assertions were not exercised.

zstd 1.5.7 configured and built, and its command-line program passed a compression and decompression round trip. libjpeg-turbo 3.2.1 built with SIMD disabled, and `tjunittest-static` exited successfully after exercising its checks. LLVM 23.1.5 configured with Clang enabled.

## x86-64 upstream subset

The selected upstream run executed 85 tests with no skips. Eighty-four passed. `kwsys.testDynamicLoader` failed because the static musl executable cannot load a shared object. An unmodified CMake build with the same pinned toolchain and static-PIE configuration failed the same test with the same message. Musl's static `dlopen` implementation reports that dynamic loading is unsupported. The registered upstream suite passed after confirming the same failure on the baseline.

## Latest automated parity differences: x86_64-unknown-linux-musl

### ninja build/build.ninja

```diff
--- reference/ninja build/build.ninja
+++ candidate/ninja build/build.ninja
@@ -168,9 +168,8 @@
 # Utility command for edit_cache

 build CMakeFiles/edit_cache.util: CUSTOM_COMMAND
-  COMMAND = cd "/qualification/graph suite/ninja build" && "/qualification/relocated cmake/bin/ccmake" -S"/qualification/graph suite/source" -B"/qualification/graph suite/ninja build"
-  DESC = Running CMake cache editor...
-  pool = console
+  COMMAND = cd "/qualification/graph suite/ninja build" && "/qualification/relocated cmake/bin/cmake" -E echo No\ interactive\ CMake\ dialog\ available.
+  DESC = No interactive CMake dialog available...
   restat = 1

 build edit_cache: phony CMakeFiles/edit_cache.util
```

### ninja-file-api.json

```diff
--- reference/ninja-file-api.json
+++ candidate/ninja-file-api.json
@@ -371,17 +371,6 @@
         "value": "CMAKE_DLLTOOL-NOTFOUND"
       },
       {
-        "name": "CMAKE_EDIT_COMMAND",
-        "properties": [
-          {
-            "name": "HELPSTRING",
-            "value": "Path to cache edit program executable."
-          }
-        ],
-        "type": "INTERNAL",
-        "value": "/qualification/relocated cmake/bin/ccmake"
-      },
-      {
         "name": "CMAKE_ERROR_DEPRECATED",
         "properties": [
           {
@@ -830,7 +819,7 @@
           }
         ],
         "type": "INTERNAL",
-        "value": "1"
+        "value": "0"
       },
       {
         "name": "CMAKE_INSTALL_SYSCONFDIR",
@@ -1262,7 +1251,7 @@
           }
         ],
         "type": "INTERNAL",
-        "value": "/usr/bin/uname"
+        "value": "/bin/uname"
       },
       {
         "name": "CMAKE_VERBOSE_MAKEFILE",
@@ -1709,11 +1698,11 @@
             "dependencies": [
               {
                 "backtrace": 2,
+                "id": "base::@6890427a1f51a3e7e1df"
+              },
+              {
+                "backtrace": 2,
                 "id": "wrapper::@6890427a1f51a3e7e1df"
-              },
-              {
-                "backtrace": 2,
-                "id": "base::@6890427a1f51a3e7e1df"
               }
             ],
             "id": "graph::@6890427a1f51a3e7e1df",
@@ -1937,7 +1926,7 @@
           {
             "directoryIndex": 0,
             "id": "graph::@6890427a1f51a3e7e1df",
-            "jsonFile": "target-graph-Release-94aad6a7ba7a6c8b9c09.json",
+            "jsonFile": "target-graph-Release-84dc3cf0c9f923a1abb5.json",
             "name": "graph",
             "projectIndex": 0
           },
```

### make-file-api.json

```diff
--- reference/make-file-api.json
+++ candidate/make-file-api.json
@@ -386,17 +386,6 @@
         "value": "CMAKE_DLLTOOL-NOTFOUND"
       },
       {
-        "name": "CMAKE_EDIT_COMMAND",
-        "properties": [
-          {
-            "name": "HELPSTRING",
-            "value": "Path to cache edit program executable."
-          }
-        ],
-        "type": "INTERNAL",
-        "value": "/qualification/relocated cmake/bin/ccmake"
-      },
-      {
         "name": "CMAKE_ERROR_DEPRECATED",
         "properties": [
           {
@@ -830,7 +819,7 @@
           }
         ],
         "type": "INTERNAL",
-        "value": "1"
+        "value": "0"
       },
       {
         "name": "CMAKE_INSTALL_SYSCONFDIR",
@@ -871,7 +860,7 @@
           }
         ],
         "type": "FILEPATH",
-        "value": "/usr/bin/make"
+        "value": "/usr/bin/gmake"
       },
       {
         "name": "CMAKE_MODULE_LINKER_FLAGS",
@@ -1266,7 +1255,7 @@
           }
         ],
         "type": "INTERNAL",
-        "value": "/usr/bin/uname"
+        "value": "/bin/uname"
       },
       {
         "name": "CMAKE_VERBOSE_MAKEFILE",
```

## Latest upstream subset: x86_64-unknown-linux-musl

Executable SHA-256: `f53bd11fb5beb68320766184ef5705986bd9ad89ee5f5177b5cfa6042160d7fa`.

Executed 85 tests. 84 passed.

The following failures also occurred in the unmodified static-PIE baseline:

- `kwsys.testDynamicLoader`

## Full upstream CTest: x86_64-unknown-linux-musl

The full upstream suite ran on an earlier x86-64 executable, before the Rustls
release-profile and section-garbage-collection changes. It was not rerun on the
published archive. The run used a copied build tree inside the network-isolated
builder. It executed 674 tests: 667 passed and seven failed. All seven failures also
occurred in the unmodified static-musl baseline under the same conditions:

- `kwsys.testDynamicLoader`
- `curl`
- `BundleUtilities`
- `CTestTestUpload`
- `CTestTestFdSetSize`
- `BootstrapTest`
- `RunCMake.NinjaMultiConfigCustomCommands`

The `curl` test requires access to `open.cdash.org`, which the sealed builder
cannot reach. The `BootstrapTest` failure occurred when its default configuration required
OpenSSL, which the builder does not provide.

## Latest upstream subset: aarch64-unknown-linux-musl

Executable SHA-256: `331eba4794afa2685a49f1be4b06889d8125a4421df9616b463ade96542e22e5`.

Executed 85 tests. 84 passed.

The following failures also occurred in the unmodified static-PIE baseline:

- `kwsys.testDynamicLoader`

## Latest automated parity differences: aarch64-unknown-linux-musl

### ninja build/build.ninja

```diff
--- reference/ninja build/build.ninja
+++ candidate/ninja build/build.ninja
@@ -168,9 +168,8 @@
 # Utility command for edit_cache

 build CMakeFiles/edit_cache.util: CUSTOM_COMMAND
-  COMMAND = cd "/qualification/graph suite/ninja build" && "/qualification/relocated cmake/bin/ccmake" -S"/qualification/graph suite/source" -B"/qualification/graph suite/ninja build"
-  DESC = Running CMake cache editor...
-  pool = console
+  COMMAND = cd "/qualification/graph suite/ninja build" && "/qualification/relocated cmake/bin/cmake" -E echo No\ interactive\ CMake\ dialog\ available.
+  DESC = No interactive CMake dialog available...
   restat = 1

 build edit_cache: phony CMakeFiles/edit_cache.util
```

### ninja-file-api.json

```diff
--- reference/ninja-file-api.json
+++ candidate/ninja-file-api.json
@@ -371,17 +371,6 @@
         "value": "CMAKE_DLLTOOL-NOTFOUND"
       },
       {
-        "name": "CMAKE_EDIT_COMMAND",
-        "properties": [
-          {
-            "name": "HELPSTRING",
-            "value": "Path to cache edit program executable."
-          }
-        ],
-        "type": "INTERNAL",
-        "value": "/qualification/relocated cmake/bin/ccmake"
-      },
-      {
         "name": "CMAKE_ERROR_DEPRECATED",
         "properties": [
           {
@@ -830,7 +819,7 @@
           }
         ],
         "type": "INTERNAL",
-        "value": "1"
+        "value": "0"
       },
       {
         "name": "CMAKE_INSTALL_SYSCONFDIR",
@@ -1262,7 +1251,7 @@
           }
         ],
         "type": "INTERNAL",
-        "value": "/usr/bin/uname"
+        "value": "/bin/uname"
       },
       {
         "name": "CMAKE_VERBOSE_MAKEFILE",
@@ -1709,11 +1698,11 @@
             "dependencies": [
               {
                 "backtrace": 2,
+                "id": "base::@6890427a1f51a3e7e1df"
+              },
+              {
+                "backtrace": 2,
                 "id": "wrapper::@6890427a1f51a3e7e1df"
-              },
-              {
-                "backtrace": 2,
-                "id": "base::@6890427a1f51a3e7e1df"
               }
             ],
             "id": "graph::@6890427a1f51a3e7e1df",
@@ -1937,7 +1926,7 @@
           {
             "directoryIndex": 0,
             "id": "graph::@6890427a1f51a3e7e1df",
-            "jsonFile": "target-graph-Release-104da5bad9bb53ceb62f.json",
+            "jsonFile": "target-graph-Release-ecf77af74e06a4e27eee.json",
             "name": "graph",
             "projectIndex": 0
           },
```

### make-file-api.json

```diff
--- reference/make-file-api.json
+++ candidate/make-file-api.json
@@ -386,17 +386,6 @@
         "value": "CMAKE_DLLTOOL-NOTFOUND"
       },
       {
-        "name": "CMAKE_EDIT_COMMAND",
-        "properties": [
-          {
-            "name": "HELPSTRING",
-            "value": "Path to cache edit program executable."
-          }
-        ],
-        "type": "INTERNAL",
-        "value": "/qualification/relocated cmake/bin/ccmake"
-      },
-      {
         "name": "CMAKE_ERROR_DEPRECATED",
         "properties": [
           {
@@ -830,7 +819,7 @@
           }
         ],
         "type": "INTERNAL",
-        "value": "1"
+        "value": "0"
       },
       {
         "name": "CMAKE_INSTALL_SYSCONFDIR",
@@ -871,7 +860,7 @@
           }
         ],
         "type": "FILEPATH",
-        "value": "/usr/bin/make"
+        "value": "/usr/bin/gmake"
       },
       {
         "name": "CMAKE_MODULE_LINKER_FLAGS",
@@ -1266,7 +1255,7 @@
           }
         ],
         "type": "INTERNAL",
-        "value": "/usr/bin/uname"
+        "value": "/bin/uname"
       },
       {
         "name": "CMAKE_VERBOSE_MAKEFILE",
@@ -1713,11 +1702,11 @@
             "dependencies": [
               {
                 "backtrace": 2,
+                "id": "base::@6890427a1f51a3e7e1df"
+              },
+              {
+                "backtrace": 2,
                 "id": "wrapper::@6890427a1f51a3e7e1df"
-              },
-              {
-                "backtrace": 2,
-                "id": "base::@6890427a1f51a3e7e1df"
               }
             ],
             "id": "graph::@6890427a1f51a3e7e1df",
@@ -1941,7 +1930,7 @@
           {
             "directoryIndex": 0,
             "id": "graph::@6890427a1f51a3e7e1df",
-            "jsonFile": "target-graph-Release-104da5bad9bb53ceb62f.json",
+            "jsonFile": "target-graph-Release-ecf77af74e06a4e27eee.json",
             "name": "graph",
             "projectIndex": 0
           },
```
