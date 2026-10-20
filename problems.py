"""problems.py - turns predictable failures into one clear message instead of a stack trace (Capstone R7).

Every script ends with  problems.run(main).  Set the environment variable DEBUG=1 to see the full
trace when you are fixing a real bug.
"""
import os
import sys


class Problem(Exception):
    """A predictable problem. The message says what to do next."""


def _first_line(error):
    return (str(error).strip().splitlines() or [type(error).__name__])[0][:200]


def run(main):
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
    except Problem as problem:
        print(f"\nProblem: {problem}")
        sys.exit(1)
    except FileNotFoundError as error:
        print(f"\nProblem: a file or folder is missing: {error.filename or error}. "
              f"Run the script from the project folder and follow the setup steps in the README.")
        sys.exit(1)
    except Exception as error:
        if os.environ.get("DEBUG"):
            raise
        text = f"{type(error).__name__} {error}".lower()
        if any(word in text for word in ("huggingface", "hf_hub", "connect", "offline", "ssl", "timed out")):
            print(f"\nProblem: a model could not be downloaded or loaded ({_first_line(error)}). "
                  f"The first run downloads about 0.3 GB, so it needs an internet connection. "
                  f"Once the models are downloaded the project also works offline.")
        else:
            print(f"\nUnexpected problem ({type(error).__name__}: {_first_line(error)}). "
                  f"Run  python verify.py  to check your setup, or set DEBUG=1 to see the full details.")
        sys.exit(1)
