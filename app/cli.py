import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--opencode-config", type=str, default="")
    args = parser.parse_args()

    if args.opencode_config:
      os.environ["STATEFUL_INTERVIEW_OPENCODE_CONFIG_PATH"] = args.opencode_config

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, reload=False)


if __name__ == "__main__":
    main()
