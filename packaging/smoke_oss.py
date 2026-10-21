"""Exercise a native OSS installation and its real CLI using isolated local data."""
import argparse
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--cli', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='staffdeck-native-smoke-') as temporary:
        data = Path(temporary)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        env = dict(os.environ, ULTRARAG_DATA_DIR=temporary, ULTRARAG_PORT=str(port),
                   ULTRARAG_PORT_RANGE_START=str(port), ULTRARAG_PORT_RANGE_END=str(port),
                   STAFFDECK_HEADLESS='true', STAFFDECK_CONFIG_DIR=str(data/'profiles'),
                   STAFFDECK_BASE_URL=f'http://127.0.0.1:{port}', STAFFDECK_TENANT_ID='tenant_demo')
        for key in ('APP_SECRET','DATABASE_URL','STAFFDECK_API_KEY','STAFFDECK_INITIAL_ADMIN_PASSWORD'):
            env.pop(key, None)
        with (data/'launcher.log').open('w') as log:
            process = subprocess.Popen([str(args.server.resolve()), 'serve'], env=env,
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(180):
                    if process.poll() is not None:
                        raise RuntimeError('Native OSS server exited before health check')
                    try:
                        with urllib.request.urlopen(env['STAFFDECK_BASE_URL']+'/api/health', timeout=2) as response:
                            if json.load(response).get('app')=='StaffDeck':break
                    except (OSError, ValueError):pass
                    time.sleep(1)
                else:raise RuntimeError('Native OSS server health timed out')
                cli = str(args.cli.resolve())
                subprocess.run([cli,'--help'],env=env,check=True,stdout=subprocess.DEVNULL)
                subprocess.run([cli,'login','--password-stdin'],input='admin\n',text=True,env=env,check=True)
                out = subprocess.check_output([cli,'agent','list'],env=env,text=True,encoding='utf-8')
                for name in ('IT','人事','行政','财务','法务'):assert name in out,name
                subprocess.run([cli,'auth','status'],env=env,check=True)
                subprocess.run([cli,'logout'],env=env,check=True)
                print('Native OSS login, default employees and CLI acceptance passed.')
            except Exception:
                log.flush()
                # Do not print settings, installation secrets or profile credentials.
                print('Native smoke failed; inspect isolated launcher logs on the runner.')
                raise
            finally:
                process.terminate()
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':main()
