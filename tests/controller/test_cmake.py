from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

import build
from buildsys.cmake import CMakeBuildError, check_capabilities
from buildsys.dependencies import DependencyError, graph_reachability


class CMakeBuildTests(unittest.TestCase):
    def test_build_rejects_networked_container(self) -> None:
        args = build._parser().parse_args(["build", "--target", "x86_64-unknown-linux-musl", "--in-container"])
        with patch.object(build.sandbox, "in_container", return_value=True), \
                patch.object(build.sandbox.socket, "if_nameindex", return_value=[(1, "lo"), (2, "eth0")]), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            args.handler(args)

    def test_dependency_reachability_uses_actual_target_edges(self) -> None:
        graph = '''digraph "CMake" {
    "node0" [ label = "cmake", shape = egg ];
    "node1" [ label = "ctest", shape = egg ];
    "node2" [ label = "cpack", shape = egg ];
    "node3" [ label = "cmcurl\\n(CURL::libcurl)", shape = octagon ];
    "node4" [ label = "cmtestonly", shape = octagon ];
    "node0" -> "node3";
    "node1" -> "node3";
    "node1" -> "node4";
}'''
        reachable = graph_reachability(graph)
        self.assertEqual(reachable["cmcurl"], {"cmake", "ctest"})
        self.assertEqual(reachable["cmtestonly"], {"ctest"})
        with self.assertRaises(DependencyError):
            graph_reachability(graph.replace('label = "cpack"', 'label = "other"'))

    def test_requires_expected_version_and_tls(self) -> None:
        check_capabilities('{"version":{"string":"4.4.5"},"tls":true,"debugger":true}', "4.4.5")
        for output in (
            '{"version":{"string":"4.4.5"},"tls":false,"debugger":true}',
            '{"version":{"string":"4.4.4"},"tls":true,"debugger":true}',
            '{"version":{"string":"4.4.5"},"tls":true,"debugger":false}',
            '{"version":{"string":"4.4.5"}}',
            'not json',
        ):
            with self.subTest(output=output), self.assertRaises(CMakeBuildError):
                check_capabilities(output, "4.4.5")


if __name__ == "__main__":
    unittest.main()
