from __future__ import annotations

import signal
import unittest
from pathlib import Path

from helpers import workspace

from buildsys.dependencies import DependencyError, graph_reachability, inventory

GRAPH = r'''
  "node0" [ label = "cmake" ];
  "node1" [ label = "ctest" ];
  "node2" [ label = "cpack" ];
  "node3" [ label = "cmcurl\n(vendor)\n(curl)" ];
  "node4" [ label = "CURL::rustls" ];
  "node5" [ label = "cmcppdap" ];
  "node6" [ label = "cmstd" ];
  "node7" [ label = "cmlibuv" ];
  "node8" [ label = "unconnected" ];
  "node0" -> "node3";
  "node3" -> "node4";
  "node0" -> "node6";
  "node1" -> "node6";
  "node1" -> "node5";
  "node1" -> "node4";
  "node2" -> "node7";
  "node2" -> "node6";
  "node6" -> "node7";
'''

ARCHIVES = (
    "/phase/libCMakeLib.a(cmFileCommand.cxx.o) definition",
    "relative/libcmcurl.a(curl_easy.o) definition",
    "librustls_ffi.a(init.o) dependency",
    "build/libcmstd.a(types.o) ordinary",
)
VERSION_FILES = {
    "Utilities/cmcurl/include/curl/curlver.h": '  # define LIBCURL_VERSION "8.17.3"\n',
    "Utilities/Scripts/update-cppdap.bash": '# update\nreadonly tag="v2026.10-rc2"\n',
    "Utilities/cmlibuv/include/uv/version.h": '#define UV_VERSION_PATCH 14\n#define UV_VERSION_MAJOR 1\n#define UV_VERSION_MINOR 51\n',
    "Utilities/KWIML/include/kwiml/version.h": '#define KWIML_VERSION_STRING "1.0.2"\n',
    "Source/cmFileCommand.cxx": '#include <cm3p/kwiml/int.h>\n',
}

REPORT = """# Bundled dependency inventory

Reachability comes from CMake's target graph. The final column records archive members in the `cmake` link map.

| Target | Version | License | Reachable from | In cmake link map |
| --- | --- | --- | --- | --- |
| `cmcppdap` | v2026.10-rc2 | Apache-2.0 | ctest | no |
| `cmcurl` | 8.17.3 | curl | cmake | yes |
| `cmlibuv` | 1.51.14 | MIT | cmake, cpack, ctest | no |
| `cmstd` | unversioned; bundled in CMake 4.4.5 | BSD-3-Clause | cmake, cpack, ctest | yes |
| `rustls-ffi` | 0.15.4 | Apache-2.0 OR ISC OR MIT | cmake, ctest | yes |
| `KWIML` (headers) | 1.0.2 | BSD-3-Clause | cmake | yes, via CMakeLib |
"""


def prepare(directory: Path) -> tuple[Path, Path]:
    for name, contents in VERSION_FILES.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    graph = directory / "graph.dot"
    graph.write_text(GRAPH)
    link_map = directory / "link.map"
    link_map.write_text("\n".join(ARCHIVES))
    return graph, link_map


class DependencyInventoryTests(unittest.TestCase):
    def test_report_contains_exact_versions_roots_and_link_evidence(self) -> None:
        with workspace() as directory:
            graph, link_map = prepare(directory)
            self.assertEqual(inventory(directory, graph, link_map, "4.4.5", "0.15.4"), REPORT)

    def test_graph_duplicate_edges_and_unresolved_targets(self) -> None:
        graph = GRAPH + '  "node0" -> "node3";\n'
        self.assertEqual(
            graph_reachability(graph),
            {
                "cmake": {"cmake"}, "ctest": {"ctest"}, "cpack": {"cpack"},
                "cmcurl": {"cmake"}, "CURL::rustls": {"cmake", "ctest"},
                "cmcppdap": {"ctest"}, "cmstd": {"cmake", "cpack", "ctest"},
                "cmlibuv": {"cmake", "cpack", "ctest"},
            },
        )
        cases = (
            (graph + '  "node0" -> "node99";\n', "dependency graph contains an unresolved target"),
            (graph + '  "node99" -> "node0";\n', "dependency graph contains an unresolved target"),
            (graph + '  "node99" [ label = "cmake" ];\n', "dependency graph requires exactly one cmake target"),
            (graph.replace('label = "cpack"', 'label = "pack"'), "dependency graph requires exactly one cpack target"),
        )
        for data, message in cases:
            with self.subTest(message=message), self.assertRaises(DependencyError) as caught:
                graph_reachability(data)
            self.assertEqual(str(caught.exception), message)

    def test_graph_terminates_on_a_cycle(self) -> None:
        def fail_on_timeout(_signal: int, _frame: object) -> None:
            self.fail("dependency graph did not finish traversing cycles")

        previous = signal.signal(signal.SIGALRM, fail_on_timeout)
        try:
            signal.setitimer(signal.ITIMER_REAL, 0.25)
            reachable = graph_reachability(GRAPH + """
              "node7" -> "node6";
              "node3" -> "node3";
              "node5" -> "node5";
              "node0" -> "node5";
            """)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        self.assertEqual(reachable["cmcurl"], {"cmake"})
        self.assertEqual(reachable["cmcppdap"], {"cmake", "ctest"})
        self.assertEqual(reachable["cmstd"], {"cmake", "cpack", "ctest"})
        self.assertEqual(reachable["cmlibuv"], {"cmake", "cpack", "ctest"})

    def test_rejects_each_missing_link_requirement(self) -> None:
        with workspace() as directory:
            graph, link_map = prepare(directory)
            for missing in ARCHIVES[:3]:
                with self.subTest(missing=missing):
                    link_map.write_text("\n".join(line for line in ARCHIVES if line != missing))
                    with self.assertRaises(DependencyError) as caught:
                        inventory(directory, graph, link_map, "4.4.5", "0.15.4")
                    self.assertEqual(str(caught.exception), "cmake link map lacks required CMake, curl, or Rustls archive members")
            link_map.write_text("\n".join(ARCHIVES).replace("cmFileCommand.cxx.o", "other.cxx.o"))
            with self.assertRaises(DependencyError) as caught:
                inventory(directory, graph, link_map, "4.4.5", "0.15.4")
            self.assertEqual(str(caught.exception), "cmake link evidence does not establish KWIML usage")
            link_map.write_text("\n".join(ARCHIVES))
            (directory / "Source/cmFileCommand.cxx").write_text("#include <memory>\n")
            with self.assertRaises(DependencyError) as caught:
                inventory(directory, graph, link_map, "4.4.5", "0.15.4")
            self.assertEqual(str(caught.exception), "cmake link evidence does not establish KWIML usage")

    def test_rejects_unclassified_or_unreachable_runtime_targets(self) -> None:
        with workspace() as directory:
            graph, link_map = prepare(directory)
            cases = (
                (GRAPH.replace('"cmstd"', '"cmunknown"').replace('"cmcppdap"', '"cmunknown2"'), "unclassified bundled targets: cmunknown, cmunknown2"),
                (GRAPH.replace('  "node3" -> "node4";\n', ''), "Rustls is not reachable from cmake in the dependency graph"),
                (GRAPH.replace('  "node3" -> "node4";\n', '').replace('  "node1" -> "node4";\n', ''), "Rustls is not reachable from cmake in the dependency graph"),
            )
            for data, message in cases:
                with self.subTest(message=message):
                    graph.write_text(data)
                    with self.assertRaises(DependencyError) as caught:
                        inventory(directory, graph, link_map, "4.4.5", "0.15.4")
                    self.assertEqual(str(caught.exception), message)

    def test_link_map_rejects_invalid_text(self) -> None:
        with workspace() as directory:
            graph, link_map = prepare(directory)
            link_map.write_bytes(link_map.read_bytes() + b"\n\xff")
            with self.assertRaises(UnicodeDecodeError):
                inventory(directory, graph, link_map, "4.4.5", "0.15.4")

    def test_rejects_ambiguous_or_missing_version_declarations(self) -> None:
        cases = (
            ("Utilities/Scripts/update-cppdap.bash", "cannot identify source revision"),
            ("Utilities/cmcurl/include/curl/curlver.h", "cannot identify LIBCURL_VERSION"),
        )
        with workspace() as directory:
            graph, link_map = prepare(directory)
            for name, message in cases:
                path = directory / name
                for content in ("# no version", VERSION_FILES[name] * 2):
                    with self.subTest(name=name, content=content):
                        path.write_text(content)
                        with self.assertRaises(DependencyError) as caught:
                            inventory(directory, graph, link_map, "4.4.5", "0.15.4")
                        self.assertEqual(str(caught.exception), f"{message} in {name}")
                path.write_text(VERSION_FILES[name])
