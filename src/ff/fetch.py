"""Download every raw input into data/raw/.

    python -m ff.fetch              # everything that is missing
    python -m ff.fetch places       # one source
    python -m ff.fetch --force      # re-download

Files are written to a .part name and renamed when complete, so an interrupted run never leaves a half-file that
looks finished. A file smaller than the source's expected minimum is rejected, which catches an error page saved
under the right name.
"""

from __future__ import annotations

import argparse
import sys
import time

import requests

from .sources import RAW, USER_AGENT, Source, all_sources

HEADERS = {"User-Agent": USER_AGENT, "Accept": "*/*"}
CHUNK = 1 << 20


def download(src: Source, force: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / src.filename
    if dest.exists() and not force and dest.stat().st_size >= src.min_bytes:
        print(f"  have  {src.filename} ({dest.stat().st_size / 1e6:,.1f} MB)")
        return
    part = dest.with_suffix(dest.suffix + ".part")
    started = time.time()
    with requests.get(src.url, params=src.params or None, headers=HEADERS, stream=True, timeout=(30, 300)) as r:
        r.raise_for_status()
        done = 0
        with open(part, "wb") as f:
            for block in r.iter_content(CHUNK):
                f.write(block)
                done += len(block)
    if done < src.min_bytes:
        part.unlink(missing_ok=True)
        raise requests.RequestException(f"{src.filename}: only {done} bytes, expected at least {src.min_bytes}")
    part.replace(dest)
    print(f"  got   {src.filename} ({done / 1e6:,.1f} MB in {time.time() - started:,.0f}s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="*", help="source keys to fetch (default: all)")
    ap.add_argument("--force", action="store_true", help="download again even if the file exists")
    args = ap.parse_args(argv)
    sources = [s for s in all_sources() if not args.keys or s.key in args.keys]
    if not sources:
        print("no matching source", file=sys.stderr)
        return 2
    for src in sources:
        print(f"{src.key}: {src.title}", flush=True)
        try:
            download(src, args.force)
        except requests.RequestException as e:
            print(f"  FAILED {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
