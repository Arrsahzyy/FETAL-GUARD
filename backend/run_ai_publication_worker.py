"""Reconcile clinician-reviewed AI results with the patient-facing feed.

Run this process with the dedicated ``fetal_guard_ai_worker`` PostgreSQL role.
It does not perform inference; it applies publication and retraction gates
after the inference worker has produced a clinician-visible result.
"""

from __future__ import annotations

import argparse
import logging
import time

from core.config import settings
from db.database import SessionLocal
from services.ai_pipeline import publish_reviewed_analysis_results


LOGGER = logging.getLogger("fetal_guard.ai_publication_worker")


def run_once(*, batch_size: int = 25) -> int:
    if settings.AI_PIPELINE_MODE != "clinician":
        raise RuntimeError("AI publication worker requires AI_PIPELINE_MODE=clinician")

    db = SessionLocal()
    try:
        reconciled = publish_reviewed_analysis_results(db, limit=batch_size)
        db.commit()
        return len(reconciled)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process one bounded batch and exit")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 100:
        parser.error("--batch-size must be between 1 and 100")
    if not 1 <= args.poll_seconds <= 300:
        parser.error("--poll-seconds must be between 1 and 300")

    logging.basicConfig(level=logging.INFO)
    while True:
        reconciled_count = run_once(batch_size=args.batch_size)
        if reconciled_count:
            LOGGER.info("Reconciled %s reviewed AI result(s)", reconciled_count)
        if args.once:
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
