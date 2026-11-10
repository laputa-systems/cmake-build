# ThinLTO provenance probe

ThinLTO was not adopted. Upstream CMake offers `CMake_BUILD_LTO`, and its Clang
compiler module selects `-flto=thin` for the pinned Clang version. The current
archive-member provenance audit cannot inspect the resulting LLVM bitcode, so a
ThinLTO build cannot pass the existing audit without additional audit support.

On the pinned x86-64 toolchain, a small `-flto=thin` object was LLVM IR
bitcode. `llvm-nm` could read its symbol, but `llvm-readelf -p .comment` on
its archive returned no member records. `buildsys.elf.audit_archives` rejected
the selected member as missing from inspection. The pinned `clang` can decode
the bitcode to textual IR and expose its target triple and compiler identity,
but the existing audit does not validate that representation.

The pinned Clang can also emit fat LTO objects containing native ELF code and
an embedded `.llvm.lto` bitcode section. Their ELF `.comment` lets the current
archive audit accept the carrier, but that alone does not establish provenance
for the bitcode. In a synthetic probe, replacing only the bitcode with a module
whose producer string was changed to `GCC: forged bitcode producer` still
passed the archive audit. Linking with LLD's `--fat-lto-objects` then used the
altered bitcode, as verified by the linked program's return value. The marker
was deliberately forged; this was not an actual GCC-produced object. The
shipped build uses neither fat LTO objects nor `--fat-lto-objects`.

This probe establishes an audit compatibility issue, not an expected speed or
size result. Full CMake ThinLTO link time, peak memory, executable size, and
runtime were not measured. Supporting the candidate would require a reviewed
way to inspect every selected bitcode member and preserve the current
provenance and linkage guarantees. The release keeps the simpler audited link.

With the x86-64 preparation phase available, the probe can be repeated from
the repository root:

```sh
mkdir -p .work/tmp/thinlto-probe
printf '%s\n' 'int probe(void) { return 42; }' > .work/tmp/thinlto-probe/probe.c
tc="$PWD/.work/build/x86_64-unknown-linux-musl/phases/prepare/toolchain/bin"
sysroot="$PWD/.work/build/x86_64-unknown-linux-musl/phases/prepare/sysroot"
"$tc/clang" --target=x86_64-unknown-linux-musl --sysroot="$sysroot" -O3 -flto=thin -c .work/tmp/thinlto-probe/probe.c -o .work/tmp/thinlto-probe/probe.o
"$tc/llvm-ar" rcs .work/tmp/thinlto-probe/probe.a .work/tmp/thinlto-probe/probe.o
printf 'reference\textracted\tsymbol\nprobe\t%s(%s)\tprobe\n' "$PWD/.work/tmp/thinlto-probe/probe.a" probe.o > .work/tmp/thinlto-probe/probe.extract
"$tc/llvm-readelf" -p .comment .work/tmp/thinlto-probe/probe.a
```

`llvm-readelf` returns successfully without reporting the bitcode member. The
controller audit then rejects the selected member:

```sh
python3 -c 'from pathlib import Path; from buildsys import elf; p=Path.cwd(); elf.audit_archives(p/".work/tmp/thinlto-probe/probe.extract", p, p/".work/build/x86_64-unknown-linux-musl/phases/prepare/toolchain/bin")'
```
