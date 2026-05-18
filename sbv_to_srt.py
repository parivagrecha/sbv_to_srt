#!/usr/bin/env python3
"""
Convert YouTube SBV subtitle files to standards-compliant SRT files.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


TIMESTAMP_PATTERN = re.compile(
    r"^\s*(?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2})\.(?P<milliseconds>\d{1,3})\s*$"
)


@dataclass(frozen=True)
class SubtitleEntry:
    start: str
    end: str
    text_lines: tuple[str, ...]


class SBVConversionError(ValueError):
    """Raised when an SBV file cannot be converted safely."""


def parse_sbv_timestamp(value: str, line_number: int) -> str:
    match = TIMESTAMP_PATTERN.match(value)
    if not match:
        raise SBVConversionError(
            f"Invalid timestamp at line {line_number}: {value!r}. "
            "Expected H:MM:SS.mmm."
        )

    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    milliseconds = match.group("milliseconds").ljust(3, "0")

    if minutes > 59 or seconds > 59:
        raise SBVConversionError(
            f"Invalid timestamp at line {line_number}: {value!r}. "
            "Minutes and seconds must be between 00 and 59."
        )

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds}"


def parse_timing_line(line: str, line_number: int) -> tuple[str, str]:
    parts = line.split(",")
    if len(parts) != 2:
        raise SBVConversionError(
            f"Invalid timing line at line {line_number}: {line!r}. "
            "Expected start and end timestamps separated by one comma."
        )

    start = parse_sbv_timestamp(parts[0], line_number)
    end = parse_sbv_timestamp(parts[1], line_number)
    if timestamp_to_milliseconds(end) < timestamp_to_milliseconds(start):
        raise SBVConversionError(
            f"Invalid timing line at line {line_number}: end time is before start time."
        )

    return start, end


def timestamp_to_milliseconds(timestamp: str) -> int:
    hours_text, minutes_text, rest = timestamp.split(":")
    seconds_text, milliseconds_text = rest.split(",")
    return (
        int(hours_text) * 3_600_000
        + int(minutes_text) * 60_000
        + int(seconds_text) * 1_000
        + int(milliseconds_text)
    )


def split_sbv_blocks(content: str) -> list[tuple[int, list[str]]]:
    blocks: list[tuple[int, list[str]]] = []
    current_block: list[str] = []
    current_start_line = 1

    for index, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.rstrip("\r")
        if line.strip() == "":
            if current_block:
                blocks.append((current_start_line, current_block))
                current_block = []
            current_start_line = index + 1
            continue

        if not current_block:
            current_start_line = index
        current_block.append(line)

    if current_block:
        blocks.append((current_start_line, current_block))

    return blocks


def parse_sbv(content: str) -> list[SubtitleEntry]:
    entries: list[SubtitleEntry] = []

    for start_line, block in split_sbv_blocks(content):
        if len(block) < 2:
            raise SBVConversionError(
                f"Invalid subtitle block starting at line {start_line}: "
                "missing subtitle text."
            )

        start, end = parse_timing_line(block[0], start_line)
        text_lines = tuple(block[1:])
        entries.append(SubtitleEntry(start=start, end=end, text_lines=text_lines))

    if not entries:
        raise SBVConversionError("The SBV file does not contain any subtitle entries.")

    return entries


def format_srt(entries: Sequence[SubtitleEntry]) -> str:
    output_lines: list[str] = []

    for index, entry in enumerate(entries, start=1):
        output_lines.append(str(index))
        output_lines.append(f"{entry.start} --> {entry.end}")
        output_lines.extend(entry.text_lines)
        output_lines.append("")

    return "\n".join(output_lines).rstrip() + "\n"


def convert_sbv_text_to_srt(content: str) -> str:
    return format_srt(parse_sbv(content))


def convert_file(input_path: Path, output_path: Path | None = None) -> Path:
    if input_path.suffix.lower() != ".sbv":
        raise SBVConversionError(f"Input file must use the .sbv extension: {input_path}")

    if not input_path.is_file():
        raise SBVConversionError(f"Input file does not exist: {input_path}")

    destination = output_path or input_path.with_suffix(".srt")
    if destination.exists() and destination.resolve() == input_path.resolve():
        raise SBVConversionError("Output path must be different from input path.")

    content = input_path.read_text(encoding="utf-8-sig")
    srt_content = convert_sbv_text_to_srt(content)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(srt_content)
    return destination


def discover_input_files(paths: Iterable[str]) -> list[Path]:
    input_files: list[Path] = []

    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            input_files.extend(sorted(path.glob("*.sbv")))
            continue
        input_files.append(path)

    return input_files


def build_output_path(input_path: Path, output: str | None, multiple_inputs: bool) -> Path | None:
    if output is None:
        return None

    output_path = Path(output)
    if multiple_inputs:
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path / input_path.with_suffix(".srt").name

    if output_path.exists() and output_path.is_dir():
        return output_path / input_path.with_suffix(".srt").name

    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert SBV subtitle files to SRT subtitle files."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help=(
            "One or more .sbv files or directories containing .sbv files. "
            "If omitted, the tool asks for an SBV file path."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output .srt file for a single input, or output directory when converting "
            "multiple files."
        ),
    )
    return parser


def ask_for_sbv_file() -> list[str]:
    while True:
        entered_path = input("Enter the path to your .sbv subtitle file: ").strip()
        if not entered_path:
            print("Please provide an .sbv file path.")
            continue

        path = Path(entered_path).expanduser()
        if path.suffix.lower() != ".sbv":
            print("Please provide a file with the .sbv extension.")
            continue

        if not path.is_file():
            print(f"File not found: {path}")
            continue

        return [str(path)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    inputs = args.inputs or ask_for_sbv_file()
    input_files = discover_input_files(inputs)

    if not input_files:
        print("Error: no SBV files found.", file=sys.stderr)
        return 1

    multiple_inputs = len(input_files) > 1
    if multiple_inputs and args.output and Path(args.output).suffix:
        print("Error: --output must be a directory when converting multiple files.", file=sys.stderr)
        return 1

    converted = 0
    try:
        for input_path in input_files:
            output_path = build_output_path(input_path, args.output, multiple_inputs)
            written_path = convert_file(input_path, output_path)
            print(f"{input_path} -> {written_path}")
            converted += 1
    except SBVConversionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"File error: {error}", file=sys.stderr)
        return 1

    return 0 if converted else 1


if __name__ == "__main__":
    raise SystemExit(main())
