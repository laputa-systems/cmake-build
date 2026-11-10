# Qualification

## Preliminary x86-64 parity

The graph and archive fixtures passed on the staged CMake 4.4.5 binary and Kitware's official 4.4.5 binary. The candidate ran in the locked Alpine builder. The reference ran in Debian trixie-slim at image index `sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`. Both used the pinned LLVM toolchain on the same native x86-64 host.

The graph fixture exercised Ninja and Unix Makefiles, compiler checks, generated files, transitive and imported targets, module and config packages, installation, downstream consumption, incremental builds, presets, file API replies, and selected system-information fields. The archive fixture created and extracted gzip, xz, bzip2, zstd, and zip archives through both `cmake -E tar` and `file()`.

The selected system-information fields matched. The Ninja build files differed in the `edit_cache` command: the reference distribution includes `ccmake`, and the staged distribution does not. The file API cache replies also differed in these fields:

- The reference included `CMAKE_EDIT_COMMAND` for `ccmake`.
- `CMAKE_INSTALL_SO_NO_EXE` was `1` in Debian and `0` in Alpine. The bundled Linux platform module selects that default from `/etc/debian_version`.
- The Makefiles generator selected `/usr/bin/make` in Debian and `/usr/bin/gmake` in Alpine.
- The detected `uname` path was `/usr/bin/uname` in Debian and `/bin/uname` in Alpine.

The Ninja codemodel listed the `base` and `wrapper` dependencies in the opposite order, and the target reply filename differed. Both generated executables and the downstream executable ran successfully. The effect of the dependency ordering on other consumers has not been established.

These runs cover the fixtures above, not the complete parity, networking, project, or upstream suites.

## Preliminary x86-64 networking

The staged CMake passed local HTTPS downloads, redirects, expected hash checks, certificate-file and certificate-directory trust, hostname rejection, verification settings, and an HTTP CONNECT proxy. The negative cases returned the expected TLS status or hash mismatch.

A separate networked container used `FetchContent` to download the locked CMake source archive and verify its SHA-256. The local tests ran with only loopback networking. These runs do not yet constitute the registered network qualification suite.

## Preliminary real-project results

fmt 12.2.1 configured and built with the staged CMake and pinned LLVM/musl toolchain. Its test run passed 18 of 21 CTest cases. `chrono-test`, `unicode-test`, and `xchar-test` failed locale assertions. A separate build with the official CMake binary and the same toolchain reproduced all three failures. The failures remain reported by the project fixture.

zstd 1.5.7 configured and built, and its command-line program passed a compression and decompression round trip. libjpeg-turbo 3.2.1 built with SIMD disabled, and `tjunittest-static` exited successfully after exercising its checks. LLVM 23.1.5 configured with Clang enabled. The complete project suite remains red because of the fmt failures.

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
