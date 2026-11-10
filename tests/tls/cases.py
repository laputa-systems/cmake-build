import http.server
import os
import pathlib
import ssl
import subprocess
import threading

root = pathlib.Path(os.environ['TLS_FIXTURE_DIR'])
root.mkdir(parents=True)
def openssl(*args):
    result = subprocess.run(['openssl', *args], cwd=root, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError(f"openssl {args[0]} failed: {result.stderr}")
openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.pem', '-days', '2', '-subj', '/CN=Test CA', '-addext', 'basicConstraints=critical,CA:TRUE')
openssl('req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'server.key', '-out', 'server.csr', '-subj', '/CN=localhost')
(root / 'ext.cnf').write_text('subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\n')
openssl('x509', '-req', '-in', 'server.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial', '-out', 'server.pem', '-days', '1', '-extfile', 'ext.cnf')
openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'other.key', '-out', 'other.pem', '-days', '2', '-subj', '/CN=Other CA', '-addext', 'basicConstraints=critical,CA:TRUE')
(root / 'index').write_text('')
(root / 'serial').write_text('01\n')
(root / 'newcerts').mkdir(exist_ok=True)
(root / 'ca.cnf').write_text(f'[ca]\ndefault_ca=issuer\n[issuer]\ndatabase={root}/index\nnew_certs_dir={root}/newcerts\ncertificate={root}/ca.pem\nprivate_key={root}/ca.key\nserial={root}/serial\ndefault_md=sha256\npolicy=policy\nx509_extensions=server\n[policy]\ncommonName=supplied\n[server]\nsubjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\n')
openssl('ca', '-batch', '-config', 'ca.cnf', '-in', 'server.csr', '-out', 'expired.pem', '-startdate', '20200101000000Z', '-enddate', '20210101000000Z')
(root / 'certs').mkdir(exist_ok=True)
(root / 'certs' / 'ca.pem').write_bytes((root / 'ca.pem').read_bytes())
(root / 'wrong-certs').mkdir()
(root / 'wrong-certs' / 'ca.pem').write_bytes((root / 'other.pem').read_bytes())

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b'ok')
        self.wfile.flush()
        self.connection.unwrap()
    def log_message(self, *args):
        pass

def check(cert, version, host, mode, ca, expected, env=None):
    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = version
    ctx.maximum_version = version
    ctx.load_cert_chain(root / cert, root / 'server.key')
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    command = [os.environ['TLS_CLIENT'], f'https://{host}:{server.server_port}/']
    if ca is not None:
        command.append(str(root / ca))
    environment = {key: value for key, value in os.environ.items() if key not in ('SSL_CERT_FILE', 'SSL_CERT_DIR')}
    result = subprocess.run(command, env={**environment, 'NO_PROXY': '*', 'no_proxy': '*', **(env or {})}, capture_output=True, text=True, timeout=15)
    server.shutdown()
    server.server_close()
    worker.join()
    if result.returncode != expected:
        raise RuntimeError(f'{cert} {version} {host} {mode}: {result.returncode} {result.stdout} {result.stderr}')
    print(f'{cert} {version.name} {host} {mode}: expected result')

check('server.pem', ssl.TLSVersion.TLSv1_3, 'localhost', 'file', 'ca.pem', 0)
check('server.pem', ssl.TLSVersion.TLSv1_2, 'localhost', 'file', 'ca.pem', 0)
check('server.pem', ssl.TLSVersion.TLSv1_3, 'localhost', 'file', 'other.pem', 60)
check('server.pem', ssl.TLSVersion.TLSv1_3, '127.0.0.1', 'file', 'ca.pem', 60)
check('expired.pem', ssl.TLSVersion.TLSv1_3, 'localhost', 'file', 'ca.pem', 60)
check('server.pem', ssl.TLSVersion.TLSv1_3, 'localhost', 'native', None, 0, {'SSL_CERT_DIR': str(root / 'certs')})
check('server.pem', ssl.TLSVersion.TLSv1_3, 'localhost', 'native', None, 60, {'SSL_CERT_DIR': str(root / 'wrong-certs')})
check('server.pem', ssl.TLSVersion.TLSv1_3, 'localhost', 'native', None, 0, {'SSL_CERT_FILE': str(root / 'ca.pem')})
check('server.pem', ssl.TLSVersion.TLSv1_3, 'localhost', 'native', None, 77, {'SSL_CERT_FILE': str(root / 'missing.pem')})
