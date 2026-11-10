from __future__ import annotations

import unittest

from buildsys.tls import TlsError, check_tree


class DependencyTests(unittest.TestCase):
    def test_graviola_closure_accepts_certificate_path_probe(self) -> None:
        check_tree("rustls-ffi v0.15.7\nrustls-graviola v0.4.0\ngraviola v0.4.4\nopenssl-probe v0.2.1\n")

    def test_rejects_other_crypto_providers_and_missing_provider(self) -> None:
        for package in ("ring", "aws-lc-rs", "aws-lc-sys", "openssl", "openssl-sys", "native-tls"):
            with self.subTest(package=package), self.assertRaises(TlsError):
                check_tree(f"rustls-ffi v0.15.7\nrustls-graviola v0.4.0\ngraviola v0.4.4\n{package} v1.0.0\n")
        with self.assertRaises(TlsError):
            check_tree("rustls-ffi v0.15.7\n")


if __name__ == "__main__":
    unittest.main()
