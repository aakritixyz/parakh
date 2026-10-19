"""Start the already installed local runtime; never pulls a model automatically."""
import os
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    bundled = root / ".runtime" / "ollama"
    binary = str(bundled) if bundled.is_file() else shutil.which("ollama")
    if binary is None:
        raise SystemExit("Install Ollama locally, then run this command again")
    environment = dict(os.environ, OLLAMA_HOST="127.0.0.1:11436", OLLAMA_MODELS=str(root / "data" / "models" / "ollama"), OLLAMA_NO_CLOUD="1", OLLAMA_NUM_PARALLEL="1", OLLAMA_MAX_LOADED_MODELS="1", LLAMA_ARG_DEVICE="none")
    os.execve(binary, [binary, "serve"], environment)


if __name__ == "__main__":
    main()
