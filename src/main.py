"""
Pipeline controller.

Commands:
  python src/main.py chunks
  python src/main.py extract
  python src/main.py validate
  python src/main.py graph
  python src/main.py neo4j
  python src/main.py all

IMPORTANT:
The `all` command still keeps every stage file-based.
Neo4j is touched only in the final stage.
"""

import subprocess
import sys


def run(script):
    subprocess.run(
        [sys.executable, f"src/{script}"],
        check=True,
    )


COMMANDS = {
    "chunks": "create_chunks.py",
    "extract": "extractor.py",
    "validate": "validator.py",
    "graph": "build_graph_json.py",
    "neo4j": "neo4j_loader.py",
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {*COMMANDS, "all"}:
        print("Usage: python src/main.py [chunks|extract|validate|graph|neo4j|all]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "all":
        for name in ["chunks", "extract", "validate", "graph", "neo4j"]:
            print(f"\n===== {name.upper()} =====")
            run(COMMANDS[name])
    else:
        run(COMMANDS[command])


if __name__ == "__main__":
    main()
