import sys
from pathlib import Path

# Make project root importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.config_loader import load_config
from backend.core.test_engine import TestEngine


def main():
    config = load_config()
    engine = TestEngine(config)
    results = engine.run()
    engine.print_summary(results)
    engine.save_results(results)


if __name__ == "__main__":
    main()
