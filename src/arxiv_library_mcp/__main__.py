"""Entry point: python -m arxiv_library_mcp"""

from arxiv_library_mcp.config import config
from arxiv_library_mcp.server import mcp


def main() -> None:
    config.ensure_dirs()
    mcp.run()


if __name__ == "__main__":
    main()
