import asyncio
import sys


async def process_output_till_done(process: asyncio.subprocess.Process, logger_func) -> tuple[bytes, bytes]:
    stdout_lines = []
    stderr_lines = []

    line_no = 0

    def log_next_line(line: bytes):
        nonlocal line_no
        logger_func((b' > ' + line).decode('utf-8').replace('\n', ''), line_no=line_no)
        line_no += 1

    async def read_stream(stream, callback, output_list):
        while True:
            line = await stream.readline()
            if line:
                callback(line)
                output_list.append(line)
            else:
                break

    tasks = [
        read_stream(process.stdout, log_next_line, stdout_lines),
        read_stream(process.stderr, log_next_line, stderr_lines)
    ]

    await asyncio.gather(*tasks)
    await process.wait()

    sys.stdout.flush()
    sys.stderr.flush()

    return b''.join(stdout_lines), b''.join(stderr_lines)
