# Patches

| Order | File | SHA-256 | Purpose |
| --- | --- | --- | --- |
| 1 | `rustls-ffi/0001-graviola-provider.patch` | `e5957e3c3f24f79db079947250685f008154dee462c6b0298c3a162321e29a87` | Select Graviola as the Rustls provider and lock its dependencies. |
| 2 | `0001-cmcurl-native-ca-fallback.patch` | `36c2244723fffd0916d18c957c6f8ba60001497a3fd65e8f75005a4772672c39` | Use the platform verifier when no CA file is selected, including `SSL_CERT_DIR`. |
