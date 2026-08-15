"""Command-line entry point for the remote serial agent."""

import argparse
import sys
from typing import BinaryIO

from hardware_serial_agent import __version__
from hardware_serial_agent.agent import SerialAgent
from hardware_serial_agent.protocol import (
    MAX_JSON_LINE_BYTES,
    AgentError,
    decode_request,
    encode_response,
    failure,
)


def run(input_stream: BinaryIO, output_stream: BinaryIO) -> int:
    """Serve protocol requests until close or end-of-file."""
    agent = SerialAgent()
    try:
        while line := input_stream.readline(MAX_JSON_LINE_BYTES + 1):
            if len(line) > MAX_JSON_LINE_BYTES:
                _discard_line_remainder(input_stream, line)
                response = failure(
                    AgentError("request_too_large", "JSON request line is too large")
                )
                should_stop = False
            else:
                try:
                    response, should_stop = agent.handle(decode_request(line))
                except AgentError as error:
                    response = failure(error)
                    should_stop = False
            output_stream.write(encode_response(response))
            output_stream.flush()
            if should_stop:
                return 0
        return 0
    finally:
        agent.close()


def main() -> int:
    """Parse CLI options and run the stdio protocol server."""
    parser = argparse.ArgumentParser(description="Expose one pyserial device over JSON Lines")
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args()
    return run(sys.stdin.buffer, sys.stdout.buffer)


def _discard_line_remainder(input_stream: BinaryIO, first_chunk: bytes) -> None:
    if first_chunk.endswith(b"\n"):
        return
    while chunk := input_stream.readline(MAX_JSON_LINE_BYTES + 1):
        if chunk.endswith(b"\n"):
            return


if __name__ == "__main__":
    raise SystemExit(main())
