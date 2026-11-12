from __future__ import annotations

import hashlib
import http.server
import os
import select
import socket
import socketserver
import ssl
import subprocess
import threading
from pathlib import Path
from typing import cast

root = Path('/qualification')
cmake = root / 'relocated cmake/bin/cmake'
work = root / 'network suite'
work.mkdir(parents=True, exist_ok=True)
openssl = '/tools/openssl'
env = {key: value for key, value in os.environ.items() if key.lower() not in {'ssl_cert_file', 'ssl_cert_dir', 'https_proxy', 'http_proxy', 'all_proxy', 'no_proxy'}}
env.update({'PATH': '/usr/bin:/bin', 'HOME': str(work), 'TMPDIR': str(work)})


def make_cert(*args: str) -> None:
    result = subprocess.run([openssl, *args], cwd=work, env=env, text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError(f'certificate generation failed: {result.stderr}')


make_cert('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.pem', '-days', '2', '-subj', '/CN=Test CA', '-addext', 'basicConstraints=critical,CA:TRUE')
make_cert('req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'server.key', '-out', 'server.csr', '-subj', '/CN=localhost')
(work / 'ext.cnf').write_text('subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\n')
make_cert('x509', '-req', '-in', 'server.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial', '-out', 'server.pem', '-days', '1', '-extfile', 'ext.cnf')
make_cert('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'other.key', '-out', 'other.pem', '-days', '2', '-subj', '/CN=Other CA', '-addext', 'basicConstraints=critical,CA:TRUE')
certs = work / 'certs'
certs.mkdir()
(certs / 'ca.pem').write_bytes((work / 'ca.pem').read_bytes())
body = b'local TLS payload\n'


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', '/payload')
            self.send_header('Content-Length', '0')
            self.end_headers()
            self.wfile.flush()
            self.connection.unwrap()
            return
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        self.connection.unwrap()

    def log_message(self, format: str, *args: object) -> None:
        pass


class Proxy(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        request = b''
        while b'\r\n\r\n' not in request:
            part = self.request.recv(4096)
            if not part:
                return
            request += part
            if len(request) > 16384:
                raise RuntimeError('proxy request too large')
        line = request.split(b'\r\n', 1)[0].decode('ascii')
        if line != f'CONNECT localhost:{server.server_port} HTTP/1.1':
            raise RuntimeError(f'unexpected proxy request: {line}')
        cast('ProxyServer', self.server).connections += 1
        with socket.create_connection(('127.0.0.1', server.server_port), timeout=10) as upstream:
            self.request.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
            sockets = (self.request, upstream)
            while True:
                ready, _, _ = select.select(sockets, [], [], 15)
                if not ready:
                    return
                for source in ready:
                    data = source.recv(65536)
                    if not data:
                        return
                    (upstream if source is self.request else self.request).sendall(data)


class ProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    connections = 0


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(work / 'server.pem', work / 'server.key')
server.socket = context.wrap_socket(server.socket, server_side=True)
proxy = ProxyServer(('127.0.0.1', 0), Proxy)
threads = [threading.Thread(target=item.serve_forever, daemon=True) for item in (server, proxy)]
for thread in threads:
    thread.start()


def download(name: str, *, host: str = 'localhost', path: str = '/payload', ca: str | None = None,
             variables: dict[str, str] | None = None, environment: dict[str, str] | None = None,
             expected_hash: str | None = None, success: bool = True) -> None:
    destination = work / f'{name}.out'
    script = work / f'{name}.cmake'
    options = f' EXPECTED_HASH SHA256={expected_hash}' if expected_hash else ''
    script.write_text(f'file(DOWNLOAD "https://{host}:{server.server_port}{path}" "{destination}" STATUS status{options})\n'
                      'list(GET status 0 code)\nmessage("DOWNLOAD_STATUS=${code}")\n')
    values = dict(variables or {})
    if ca:
        values['CMAKE_TLS_CAINFO'] = str(work / ca)
    result = subprocess.run([str(cmake), *(f'-D{key}={value}' for key, value in values.items()), '-P', str(script)],
                            cwd=work, env={**env, **(environment or {})}, text=True, capture_output=True, timeout=45, check=False)
    passed = result.returncode == 0 and 'DOWNLOAD_STATUS=0' in result.stderr and destination.is_file() and destination.read_bytes() == body
    if success:
        correct = passed
    elif expected_hash:
        correct = result.returncode != 0 and 'file DOWNLOAD HASH mismatch' in result.stderr
    else:
        correct = result.returncode == 0 and 'DOWNLOAD_STATUS=60' in result.stderr
    if not correct:
        raise RuntimeError(f'{name}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    print(f'{name}: {"success" if success else "expected failure"}')


try:
    digest = hashlib.sha256(body).hexdigest()
    download('cainfo', ca='ca.pem', expected_hash=digest)
    download('redirect', path='/redirect', ca='ca.pem', expected_hash=digest)
    download('hash-mismatch', ca='ca.pem', expected_hash='0' * 64, success=False)
    download('untrusted', ca='other.pem', success=False)
    download('hostname', host='127.0.0.1', ca='ca.pem', success=False)
    download('ssl-cert-file', environment={'SSL_CERT_FILE': str(work / 'ca.pem')})
    download('ssl-cert-dir', environment={'SSL_CERT_DIR': str(certs)})
    download('default-verification', success=False)
    download('verify-off', variables={'CMAKE_TLS_VERIFY': 'OFF'})
    download('verify-on', variables={'CMAKE_TLS_VERIFY': 'ON'}, ca='other.pem', success=False)
    download('https-proxy', ca='ca.pem', environment={'https_proxy': f'http://127.0.0.1:{proxy.server_address[1]}'})
    if proxy.connections != 1:
        raise RuntimeError(f'expected one CONNECT through the proxy, got {proxy.connections}')
finally:
    for item in (server, proxy):
        item.shutdown()
        item.server_close()
    for thread in threads:
        thread.join(timeout=5)
print('local HTTPS qualification: 11 cases passed')
