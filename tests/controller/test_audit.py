from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import build
from buildsys import elf, toolchain
from buildsys.targets import native_target


class ElfAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.target = native_target()
        cls.phase = build._target_root(cls.target) / 'phases'
        cls.tools = cls.phase / 'prepare/toolchain/bin'
        cls.temporary = tempfile.TemporaryDirectory(dir=build.WORK / 'tmp')
        cls.root = Path(cls.temporary.name)
        cls.compiler = [str(cls.tools / 'clang'), *toolchain.flags(cls.target, cls.phase / 'prepare/sysroot')]
        cls.source = cls.root / 'main.c'
        cls.source.write_text('int main(void) { return 0; }\n')
        cls.link('clean', '-static-pie')
        cls.link('execstack', '-static-pie', '-Wl,-z,execstack')
        cls.link('rpath', '-static-pie', '-Wl,-rpath,/home/fixture')
        library = cls.root / 'libstdc++.so.6'
        subprocess.run([*cls.compiler, '-shared', '-nostdlib', '-fPIC', '-Wl,-soname,libstdc++.so.6', '-x', 'c', '-', '-o', str(library)],
                       input='int fixture(void) { return 0; }\n', text=True, capture_output=True, check=True)
        cls.link('libstdcpp', f'-L{cls.root}', '-Wl,--no-as-needed', '-l:libstdc++.so.6')

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @classmethod
    def link(cls, name: str, *options: str) -> None:
        subprocess.run([*cls.compiler, '-Wl,-z,relro,-z,now,-z,noexecstack', str(cls.source), *options, '-o', str(cls.root / name)],
                       text=True, capture_output=True, check=True)

    def test_real_cmake_passes_the_native_audit(self) -> None:
        elf.audit(self.phase / 'cmake/build/bin/cmake', self.target, self.tools)

    def test_debug_stripping_preserves_the_audited_executable(self) -> None:
        original = self.phase / 'cmake/build/bin/cmake'
        stripped = self.root / 'cmake-stripped'
        elf.strip_debug(original, stripped, self.target, self.tools)
        before = subprocess.check_output([str(self.tools / 'llvm-readelf'), '-S', str(original)], text=True)
        after = subprocess.check_output([str(self.tools / 'llvm-readelf'), '-S', str(stripped)], text=True)
        self.assertIn('.debug_info', before)
        self.assertNotIn('.debug_info', after)
        self.assertLess(stripped.stat().st_size, original.stat().st_size)

    def test_rejects_gcc_object_selected_from_archive(self) -> None:
        archive = self.root / 'fixture.a'
        fixture = build.ROOT / 'tests/audit/gcc-x86_64.o'
        subprocess.run([str(self.tools / 'llvm-ar'), 'rcs', str(archive), str(fixture)], check=True)
        extract = self.root / 'extract'
        extract.write_text(f'reference\textracted\tsymbol\nprobe\t{archive}({fixture.name})\tgcc_fixture\n')
        with self.assertRaisesRegex(elf.AuditError, 'GCC compiler provenance'):
            elf.audit_archives(extract, self.root, self.tools)
        unapproved = self.root / 'libstdc++.a'
        subprocess.run([str(self.tools / 'llvm-ar'), 'rcs', str(unapproved), str(fixture)], check=True)
        extract.write_text(f'reference\textracted\tsymbol\nprobe\t{unapproved}({fixture.name})\tgcc_fixture\n')
        with self.assertRaisesRegex(elf.AuditError, 'unapproved linked archive'):
            elf.audit_archives(extract, self.root, self.tools)
        if self.target.machine != 'x86_64':
            native_source = self.root / 'native-contaminated.c'
            native_source.write_text('__asm__(".ident \\"GCC: audit contamination\\""); int gcc_fixture(void) { return 7; }\n')
            native_object = self.root / 'native-contaminated.o'
            subprocess.run([*self.compiler, '-c', str(native_source), '-o', str(native_object)], capture_output=True, check=True)
            archive = self.root / 'native-contaminated.a'
            subprocess.run([str(self.tools / 'llvm-ar'), 'rcs', str(archive), str(native_object)], check=True)
        source = self.root / 'uses-gcc.c'
        source.write_text('int gcc_fixture(void); int main(void) { return gcc_fixture(); }\n')
        obj = self.root / 'uses-gcc.o'
        subprocess.run([*self.compiler, '-c', str(source), '-o', str(obj)], capture_output=True, check=True)
        output = self.root / 'gcc-program'
        command = [*self.compiler, '-static-pie', '-Xlinker', '-Map', '-Xlinker', str(self.root / 'gcc.map'),
                   '-Xlinker', f'--why-extract={self.root / "gcc.extract"}', str(obj), str(archive), '-o', str(output)]
        result = subprocess.run([sys.executable, '-m', 'buildsys.elf', str(self.tools), *command],
                                cwd=self.root, text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('GCC compiler provenance', result.stderr)
        self.assertFalse(output.exists())

    def test_rejects_contaminated_elf_files(self) -> None:
        elf.audit(self.root / 'clean', self.target, self.tools)
        for name, message in [('execstack', 'GNU stack'), ('rpath', 'RPATH'), ('libstdcpp', 'dynamic dependency')]:
            with self.subTest(name=name), self.assertRaisesRegex(elf.AuditError, message):
                elf.audit(self.root / name, self.target, self.tools)
        binary = (self.root / 'clean').read_bytes()
        wrong_machine = bytearray(binary)
        wrong_machine[18:20] = (183 if self.target.elf_machine == 62 else 62).to_bytes(2, 'little')
        (self.root / 'wrong-machine').write_bytes(wrong_machine)
        with self.assertRaisesRegex(elf.AuditError, 'machine'):
            elf.audit(self.root / 'wrong-machine', self.target, self.tools)
        (self.root / 'host-path').write_bytes(binary + b'\0/home/audit-fixture\0')
        with self.assertRaisesRegex(elf.AuditError, 'host path'):
            elf.audit(self.root / 'host-path', self.target, self.tools)
        (self.root / 'version-identifiers').write_bytes(binary + b'\0OpenSSL/\0openssl\0archive_openssl_version\0openssl_probe::probe\0')
        elf.audit(self.root / 'version-identifiers', self.target, self.tools)
        (self.root / 'openssl-text').write_bytes(binary + b'\0OpenSSL engine enabled\0')
        with self.assertRaisesRegex(elf.AuditError, 'OpenSSL text'):
            elf.audit(self.root / 'openssl-text', self.target, self.tools)

    def test_discards_output_if_final_link_selects_other_members(self) -> None:
        obj = self.root / 'clean-member.o'
        archive = self.root / 'clean-members.a'
        subprocess.run([*self.compiler, '-c', str(self.source), '-o', str(obj)], capture_output=True, check=True)
        subprocess.run([str(self.tools / 'llvm-ar'), 'rcs', str(archive), str(obj)], check=True)
        linker = self.root / 'changing-linker.py'
        linker.write_text('''import sys
from pathlib import Path
args = sys.argv[1:]
output = Path(args[args.index("-o") + 1])
extract = Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("--why-extract=")))
member = "clean-member.o" if "link-audit-" in str(output) else "other.o"
extract.write_text(f"reference\\textracted\\tsymbol\\nprobe\\t{sys.argv[1]}({member})\\tmain\\n")
output.write_bytes(b"linked")
''')
        output = self.root / 'changed-output'
        command = [sys.executable, str(linker), str(archive), '-Map', '-Xlinker', str(self.root / 'probe.map'),
                   f'--why-extract={self.root / "changed.extract"}', '-o', str(output)]
        result = subprocess.run([sys.executable, '-m', 'buildsys.elf', str(self.tools), *command],
                                cwd=self.root, text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('different archive members', result.stderr)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
