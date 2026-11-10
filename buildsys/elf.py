"""Audit native ELF linkage, hardening, and compiler provenance."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .targets import Target


class AuditError(Exception):
    pass


def _tool(tool: Path, *arguments: str) -> str:
    result = subprocess.run([str(tool), *map(str, arguments)], text=True, capture_output=True, check=False)
    if result.returncode:
        raise AuditError(f'{tool.name} failed ({result.returncode}): {result.stderr.strip()}')
    return result.stdout


def audit(binary: Path, target: Target, tools: Path) -> None:
    try:
        report = json.loads(_tool(tools / 'llvm-readelf', '-h', '-l', '-d', '-S', '--elf-output-style=JSON', binary))
        if len(report) != 1:
            raise AuditError('expected exactly one ELF')
        document = report[0]
        header = document['ElfHeader']
        headers = [item['ProgramHeader'] for item in document['ProgramHeaders']]
        dynamic = document.get('DynamicSection', [])
        sections = {item['Section']['Name']['Name'] for item in document['Sections']}
    except (ValueError, KeyError, TypeError) as error:
        raise AuditError(f'invalid ELF report for {binary}') from error
    if header['Machine']['Value'] != target.elf_machine:
        raise AuditError('ELF machine does not match the target')
    if not header['Type'].startswith('SharedObject'):
        raise AuditError('ELF must be PIE')
    kinds = {item['Type']['Name']: item for item in headers}
    stack = kinds.get('PT_GNU_STACK')
    if stack is None or stack['Flags']['Value'] & 1:
        raise AuditError('ELF has an executable or missing GNU stack')
    if 'PT_GNU_RELRO' not in kinds:
        raise AuditError('ELF lacks GNU RELRO')
    entries = {item['Type']: item for item in dynamic}
    flags = {flag for item in dynamic for flag in item.get('Flags', [])}
    if 'BIND_NOW' not in flags and 'NOW' not in flags:
        raise AuditError('ELF lacks immediate binding')
    if 'PIE' not in flags:
        raise AuditError('ELF is not marked PIE')
    if 'RPATH' in entries or 'RUNPATH' in entries:
        raise AuditError('ELF contains RPATH or RUNPATH')
    needed = {item['Library'] for item in dynamic if item['Type'] == 'NEEDED'}
    interpreter = kinds.get('PT_INTERP')
    if interpreter is None:
        if needed:
            raise AuditError('static PIE has dynamic dependencies')
    else:
        with binary.open('rb') as file:
            file.seek(interpreter['Offset'])
            loader = file.read(interpreter['FileSize']).rstrip(b'\0').decode('ascii')
        if loader != target.musl_loader or not needed <= {Path(target.musl_loader).name.replace('ld-musl-', 'libc.musl-')}:
            raise AuditError('ELF uses an unapproved interpreter or dynamic dependency')
    if '.gnu.version_r' in sections:
        raise AuditError('ELF contains unapproved symbol versions')
    if '.comment' not in sections:
        raise AuditError('ELF lacks compiler provenance')
    comment = _tool(tools / 'llvm-readelf', '--string-dump=.comment', binary)
    _tool(tools / 'llvm-objdump', '-s', '-j', '.comment', binary)
    if 'GCC:' in comment:
        raise AuditError('ELF contains GCC compiler provenance')
    symbols = _tool(tools / 'llvm-nm', binary)
    if re.search(r'(?m)\s(?:OPENSSL_|SSL_|EVP_|BIO_|X509_|CRYPTO_|PEM_|ASN1_|ERR_get_error|ERR_error_string|ERR_peek_error|ERR_clear_error)[A-Za-z0-9_]*$', symbols):
        raise AuditError('ELF contains OpenSSL API symbols')
    strings = _tool(tools / 'llvm-strings', binary)
    if re.search(r'GLIBC_[0-9]|GLIBCXX_[0-9]|CXXABI_[0-9]|\blib(?:gcc(?:_s)?|stdc\+\+|ssl|crypto)\.(?:so|a)', strings):
        raise AuditError('ELF contains an unapproved runtime or OpenSSL library')
    version_identifiers = {'openssl', 'openssl/', 'archive_openssl_version'}
    for line in strings.splitlines():
        remaining = re.sub(r'openssl[_-]probe|try_init_openssl_env_vars', '', line, flags=re.IGNORECASE)
        if 'openssl' in remaining.lower() and line.lower() not in version_identifiers:
            raise AuditError('ELF contains unapproved OpenSSL text')
    if re.search(r'/home/|/src/\.work(?:/|\b)|\.work/', strings):
        raise AuditError('ELF contains a build-host path')


def strip_debug(binary: Path, destination: Path, target: Target, tools: Path) -> None:
    if binary.resolve() == destination.resolve():
        raise AuditError('stripping requires a separate destination')
    try:
        _tool(tools / 'llvm-strip', '--strip-debug', '-o', destination, binary)
        audit(destination, target, tools)
    except (AuditError, OSError):
        destination.unlink(missing_ok=True)
        raise


def _selected_members(extract: Path) -> set[str]:
    lines = extract.read_text().splitlines()
    if not lines or lines[0] != 'reference\textracted\tsymbol':
        raise AuditError('invalid linker extraction evidence')
    selected = set()
    for line in lines[1:]:
        fields = line.split('\t', 2)
        member = re.fullmatch(r'(.*\.a)\(([^()]*)\)', fields[1]) if len(fields) == 3 else None
        if member is None:
            raise AuditError('invalid extracted archive member')
        selected.add(fields[1])
    if not selected:
        raise AuditError('linker extracted no archive members')
    return selected


def audit_archives(extract: Path, directory: Path, tools: Path) -> None:
    selected: dict[Path, set[str]] = {}
    for name in _selected_members(extract):
        member = re.fullmatch(r'(.*\.a)\(([^()]*)\)', name)
        if member is None:
            raise AuditError('invalid extracted archive member')
        archive = Path(member.group(1))
        if not archive.is_absolute():
            archive = directory / archive
        selected.setdefault(archive, set()).add(member.group(2))
    for archive, members in selected.items():
        if re.match(r'lib(?:gcc(?:_s)?|stdc\+\+|ssl|crypto)\.', archive.name):
            raise AuditError(f'unapproved linked archive: {archive}')
        output = _tool(tools / 'llvm-readelf', '-p', '.comment', archive)
        records = re.split(r'(?m)^File: ', output)[1:]
        seen = set()
        for record in records:
            name, _, comment = record.partition('\n')
            match = re.fullmatch(r'.*\(([^()]*)\)', name)
            if not match:
                raise AuditError(f'invalid archive member report: {name}')
            member = match.group(1)
            if member in members:
                seen.add(member)
                if 'GCC:' in comment:
                    raise AuditError(f'GCC compiler provenance in {archive}({member})')
        if seen != members:
            raise AuditError(f'archive members missing from inspection: {archive}: {sorted(members - seen)}')


def prelink(tools: Path, command: list[str]) -> int:
    with tempfile.TemporaryDirectory(prefix='link-audit-', dir=Path.cwd()) as temporary:
        scratch = Path(temporary)
        probe = command.copy()
        try:
            probe[probe.index('-o') + 1] = str(scratch / 'cmake')
            map_index = probe.index('-Map')
            probe[map_index + 2] = str(scratch / 'cmake.map')
            extract_index = next(index for index, item in enumerate(probe) if item.startswith('--why-extract='))
        except (ValueError, IndexError, StopIteration) as error:
            raise AuditError('link command lacks output or extraction evidence') from error
        extract = scratch / 'cmake.extract'
        probe[extract_index] = f'--why-extract={extract}'
        for index, item in enumerate(probe):
            if item.startswith('--dependency-file='):
                probe[index] = f'--dependency-file={scratch / "link.d"}'
        result = subprocess.run(probe, check=False)
        if result.returncode:
            return result.returncode
        audit_archives(extract, Path.cwd(), tools)
        selected = _selected_members(extract)
        result = subprocess.run(command, check=False)
        if result.returncode:
            return result.returncode
        final_extract = Path(command[extract_index].split('=', 1)[1])
        try:
            actual = _selected_members(final_extract)
        except (AuditError, OSError):
            Path(command[command.index('-o') + 1]).unlink(missing_ok=True)
            raise
        if actual != selected:
            Path(command[command.index('-o') + 1]).unlink(missing_ok=True)
            raise AuditError('final link selected different archive members from the audited probe')
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(prelink(Path(sys.argv[1]), sys.argv[2:]))
    except AuditError as error:
        print(f'link audit: {error}', file=sys.stderr)
        raise SystemExit(1)
