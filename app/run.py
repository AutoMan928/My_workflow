"""
CLI entry point.

Usage:
  python -m app.run --slot morning
  python -m app.run --slot morning --category banking
  python -m app.run --slot morning --dry-run
"""
import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="News platform pipeline")
    parser.add_argument("--slot", required=True, choices=["morning", "evening"])
    parser.add_argument("--category", default="all",
                        help="Category slug or 'all'")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip real API calls")
    args = parser.parse_args()

    from app.config import get_config
    from app.models.base import init_db, SessionLocal
    from app.scheduler.pipeline import run_pipeline

    Path("data").mkdir(exist_ok=True)
    init_db()

    cfg = get_config()
    categories = cfg.categories
    if args.category != "all":
        categories = [c for c in categories if c.slug == args.category]
        if not categories:
            logger.error("Category %r not found", args.category)
            sys.exit(1)

    db = SessionLocal()
    try:
        summary = run_pipeline(args.slot, categories, db, cfg,
                               dry_run=args.dry_run)
        logger.info("Done: %s", summary)
    finally:
        db.close()


if __name__ == "__main__":
    main()
