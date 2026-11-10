"""Derive bundled dependency reachability from CMake and linker output."""

from __future__ import annotations

import re
from pathlib import Path


class DependencyError(Exception):
    pass


_LIBRARIES = {
    "cmbzip2": ("Utilities/cmbzip2/bzlib_private.h", ("BZ_VERSION",), "bzip2-1.0.6"),
    "cmcppdap": ("Utilities/Scripts/update-cppdap.bash", ("@tag",), "Apache-2.0"),
    "cmcurl": ("Utilities/cmcurl/include/curl/curlver.h", ("LIBCURL_VERSION",), "curl"),
    "cmexpat": ("Utilities/cmexpat/lib/expat.h", ("XML_MAJOR_VERSION", "XML_MINOR_VERSION", "XML_MICRO_VERSION"), "MIT"),
    "cmjsoncpp": ("Utilities/cmjsoncpp/include/json/version.h", ("JSONCPP_VERSION_STRING",), "MIT OR public domain"),
    "cmlibarchive": ("Utilities/cmlibarchive/libarchive/archive.h", ("ARCHIVE_VERSION_ONLY_STRING",), "BSD-2-Clause, BSD-3-Clause, public domain and exceptions; see Utilities/cmlibarchive/COPYING"),
    "cmliblzma": ("Utilities/cmliblzma/liblzma/api/lzma/version.h", ("LZMA_VERSION_MAJOR", "LZMA_VERSION_MINOR", "LZMA_VERSION_PATCH"), "0BSD"),
    "cmlibrhash": ("Utilities/Scripts/update-librhash.bash", ("@tag",), "0BSD"),
    "cmlibuv": ("Utilities/cmlibuv/include/uv/version.h", ("UV_VERSION_MAJOR", "UV_VERSION_MINOR", "UV_VERSION_PATCH"), "MIT"),
    "cmllpkgc": ("Utilities/Scripts/update-llpkgc.bash", ("@tag",), "BSD-3-Clause"),
    "cmnghttp2": ("Utilities/cmnghttp2/lib/includes/nghttp2/nghttp2ver.h", ("NGHTTP2_VERSION",), "MIT"),
    "cmstd": (None, (), "BSD-3-Clause"),
    "cmsys": (None, (), "BSD-3-Clause; see Source/kwsys/Copyright.txt"),
    "cmzlib": ("Utilities/cmzlib/zlib.h", ("ZLIB_VERSION",), "Zlib"),
    "cmzstd": ("Utilities/cmzstd/lib/zstd.h", ("ZSTD_VERSION_MAJOR", "ZSTD_VERSION_MINOR", "ZSTD_VERSION_RELEASE"), "BSD-3-Clause"),
}


def graph_reachability(graph: str) -> dict[str, set[str]]:
    nodes = dict(re.findall(r'^\s*"(node[0-9]+)"\s*\[\s*label\s*=\s*"([^"\n]+)"', graph, re.MULTILINE))
    names = {node: label.split("\\n", 1)[0] for node, label in nodes.items()}
    roots = {}
    for name in ("cmake", "ctest", "cpack"):
        matches = [node for node, label in names.items() if label == name]
        if len(matches) != 1:
            raise DependencyError(f"dependency graph requires exactly one {name} target")
        roots[name] = matches[0]
    edges: dict[str, set[str]] = {}
    for source, destination in re.findall(r'^\s*"(node[0-9]+)"\s*->\s*"(node[0-9]+)"', graph, re.MULTILINE):
        if source not in names or destination not in names:
            raise DependencyError("dependency graph contains an unresolved target")
        edges.setdefault(source, set()).add(destination)
    reachable: dict[str, set[str]] = {}
    for root, start in roots.items():
        pending = [start]
        visited = set()
        while pending:
            node = pending.pop()
            if node in visited:
                continue
            visited.add(node)
            reachable.setdefault(names[node], set()).add(root)
            pending.extend(edges.get(node, ()))
    return reachable


def _version(source: Path, path: str | None, macros: tuple[str, ...], cmake_version: str) -> str:
    if path is None:
        return f"unversioned; bundled in CMake {cmake_version}"
    text = (source / path).read_text()
    if macros == ("@tag",):
        tags = re.findall(r'^readonly tag="([^"]+)"', text, re.MULTILINE)
        if len(tags) != 1:
            raise DependencyError(f"cannot identify source revision in {path}")
        return tags[0]
    parts = []
    for macro in macros:
        matches = re.findall(r'^\s*#\s*define\s+' + re.escape(macro) + r'\s+"?([0-9]+(?:\.[0-9]+)*)', text, re.MULTILINE)
        if len(matches) != 1:
            raise DependencyError(f"cannot identify {macro} in {path}")
        parts.append(matches[0])
    return ".".join(parts)


def inventory(source: Path, graph: Path, link_map: Path, cmake_version: str, rustls_version: str) -> str:
    reachable = graph_reachability(graph.read_text())
    unknown = sorted(name for name in reachable if name.startswith("cm") and name != "cmake" and name not in _LIBRARIES)
    if unknown:
        raise DependencyError(f"unclassified bundled targets: {', '.join(unknown)}")
    map_text = link_map.read_text(errors="strict")
    archives = {Path(path).name for path in re.findall(r'([^\s()]+\.a)\([^()]+\)', map_text)}
    if "libCMakeLib.a" not in archives or "libcmcurl.a" not in archives or "librustls_ffi.a" not in archives:
        raise DependencyError("cmake link map lacks required CMake, curl, or Rustls archive members")
    if "cmake" not in reachable.get("CURL::rustls", set()):
        raise DependencyError("Rustls is not reachable from cmake in the dependency graph")
    rows = []
    for name, (path, macros, license_name) in sorted(_LIBRARIES.items()):
        if name not in reachable:
            continue
        version = _version(source, path, macros, cmake_version)
        roots = ", ".join(sorted(reachable[name]))
        extracted = "yes" if f"lib{name}.a" in archives else "no"
        rows.append(f"| `{name}` | {version} | {license_name} | {roots} | {extracted} |")
    roots = ", ".join(sorted(reachable["CURL::rustls"]))
    rows.append(f"| `rustls-ffi` | {rustls_version} | Apache-2.0 OR ISC OR MIT | {roots} | yes |")
    if "libCMakeLib.a(cmFileCommand.cxx.o)" not in map_text or "<cm3p/kwiml/int.h>" not in (source / "Source/cmFileCommand.cxx").read_text():
        raise DependencyError("cmake link evidence does not establish KWIML usage")
    version = _version(source, "Utilities/KWIML/include/kwiml/version.h", ("KWIML_VERSION_STRING",), cmake_version)
    rows.append(f"| `KWIML` (headers) | {version} | BSD-3-Clause | cmake | yes, via CMakeLib |")
    if not rows:
        raise DependencyError("dependency inventory is empty")
    return "\n".join([
        "# Bundled dependency inventory", "",
        "Reachability comes from CMake's target graph. The final column records archive members in the `cmake` link map.", "",
        "| Target | Version | License | Reachable from | In cmake link map |",
        "| --- | --- | --- | --- | --- |", *rows, "",
    ])
