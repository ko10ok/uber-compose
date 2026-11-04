import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import sys


@dataclass
class VedroRunResult:
    returncode: int
    stdout: str
    stderr: str


class CliRunner:
    async def run_vedro(self, project_dir: Path, args: list[str] | None = None) -> VedroRunResult:
        """
        Runs `vedro run` as a real, independent subprocess against a standalone project
        directory (own vedro.cfg.py + scenarios), using the same python interpreter the
        outer e2e suite runs under - so the installed `uber-compose` package (and its
        vedro plugin) is picked up exactly like in a real user project.
        """
        args = args if args is not None else ['run']

        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'vedro', *args,
            cwd=str(project_dir),
            env=os.environ.copy(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        return VedroRunResult(
            returncode=process.returncode,
            stdout=stdout.decode('utf-8'),
            stderr=stderr.decode('utf-8'),
        )
