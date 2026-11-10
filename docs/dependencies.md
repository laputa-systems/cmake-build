# Bundled dependency inventory

Reachability comes from CMake's target graph. The final column records archive members in the `cmake` link map.

| Target | Version | License | Reachable from | In cmake link map |
| --- | --- | --- | --- | --- |
| `cmbzip2` | 1.0.8 | bzip2-1.0.6 | cmake, cpack, ctest | yes |
| `cmcppdap` | c69444ed76f7468b232ac4f989cb8f2bdc100185 | Apache-2.0 | cmake, cpack, ctest | yes |
| `cmcurl` | 8.20.0 | curl | cmake, cpack, ctest | yes |
| `cmexpat` | 2.7.3 | MIT | cmake, cpack, ctest | yes |
| `cmjsoncpp` | 1.9.6 | MIT OR public domain | cmake, cpack, ctest | yes |
| `cmlibarchive` | 3.8.6 | BSD-2-Clause, BSD-3-Clause, public domain and exceptions; see Utilities/cmlibarchive/COPYING | cmake, cpack, ctest | yes |
| `cmliblzma` | 5.6.3 | 0BSD | cmake, cpack, ctest | yes |
| `cmlibrhash` | v1.4.4 | 0BSD | cmake, cpack, ctest | yes |
| `cmlibuv` | 1.52.0 | MIT | cmake, cpack, ctest | yes |
| `cmllpkgc` | 7958a1de42b9eec04676d547f6fcf5daa425fbcc | BSD-3-Clause | cmake, cpack, ctest | yes |
| `cmnghttp2` | 1.68.0 | MIT | cmake, cpack, ctest | yes |
| `cmstd` | unversioned; bundled in CMake 4.4.5 | BSD-3-Clause | cmake, cpack, ctest | no |
| `cmsys` | unversioned; bundled in CMake 4.4.5 | BSD-3-Clause; see Source/kwsys/Copyright.txt | cmake, cpack, ctest | yes |
| `cmzlib` | 1.3.1 | Zlib | cmake, cpack, ctest | yes |
| `cmzstd` | 1.5.7 | BSD-3-Clause | cmake, cpack, ctest | yes |
| `rustls-ffi` | 0.15.7 | Apache-2.0 OR ISC OR MIT | cmake, cpack, ctest | yes |
| `KWIML` (headers) | 1.0.0 | BSD-3-Clause | cmake | yes, via CMakeLib |
