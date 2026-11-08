"""python -m app [--mock] [--port 8000]"""

import argparse
import os

import uvicorn


def main():
    ap = argparse.ArgumentParser(description="Run SockLock Hook Lab locally")
    ap.add_argument("--mock", action="store_true", help="fixture output, no API key needed")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if args.mock:
        os.environ["MOCK_LLM"] = "1"
    print(f"Hook Lab on http://127.0.0.1:{args.port}" + ("  (mock mode)" if args.mock else ""))
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
