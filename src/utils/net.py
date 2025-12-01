# src/utils/net.py
from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Optional


def free_port(port: int, name_hint: Optional[str] = None, timeout: float = 3.0) -> bool:
    """
    Libera 'port' matando processos que estejam LISTEN nessa porta.
    - Se name_hint for passado (ex.: "src.server"), só mata PIDs cujo comando contém esse texto.
    - Tenta SIGTERM, espera, e se ainda estiver ocupada, SIGKILL.
    Retorna True se a porta ficou livre (ou já estava), False se não foi possível.
    """
    def _pids_listening(p: int) -> list[int]:
        # -t : apenas PIDs; -iTCP:PORT; -sTCP:LISTEN
        proc = subprocess.run(
            ["bash", "-lc", f"lsof -tiTCP:{p} -sTCP:LISTEN"],
            capture_output=True, text=True, check=False,
        )
        out = proc.stdout.strip()
        return [int(x) for x in out.split()] if out else []

    def _cmdline(pid: int) -> str:
        proc = subprocess.run(["ps", "-p", str(pid), "-o", "args="],
                              capture_output=True, text=True, check=False)
        return (proc.stdout or "").strip()

    pids = _pids_listening(port)
    if not pids:
        return True

    # filtra por name_hint, se fornecido
    if name_hint:
        filtered = []
        for pid in pids:
            try:
                cmd = _cmdline(pid)
                if name_hint in cmd:
                    filtered.append(pid)
            except Exception:
                pass
        pids = filtered

    # evita matar o próprio processo por engano
    this_pid = os.getpid()
    pids = [pid for pid in pids if pid != this_pid]

    if not pids:
        # Nada elegível para matar (outra app na porta); não force
        return False

    # SIGTERM
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            # sem permissão para esse PID
            pass

    # espera liberar
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pids_listening(port):
            return True
        time.sleep(0.1)

    # SIGKILL como último recurso
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass

    # checa de novo
    return not _pids_listening(port)


def split_endpoint(ep: str) -> tuple[str, int, str]:
    """
    Divide 'opc.tcp://host:port/path' -> (host, port, path)
    """
    prefix = "opc.tcp://"
    assert ep.startswith(prefix)
    rest = ep[len(prefix):]
    if "/" in rest:
        hostport, path = rest.split("/", 1)
        path = "/" + path
    else:
        hostport, path = rest, ""
    if ":" in hostport:
        host, port_s = hostport.split(":", 1)
        try:
            port = int(port_s)
        except ValueError:
            port = 4840
    else:
        host, port = hostport, 4840
    return host, port, path
