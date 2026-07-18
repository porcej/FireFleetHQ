#!/usr/bin/env python
"""
CLI helper: login to PSTrax and capture /department-status-report.php response.

Usage:
  python capture_department_status.py
  python capture_department_status.py --out "PSTrax Example/sample.txt"

Requires PSTrax credentials already saved in Settings (scrape_config).
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.scraper import perform_apparatus_scrape


def main():
    parser = argparse.ArgumentParser(description='Capture PSTrax department status report sample')
    parser.add_argument(
        '--out',
        default=None,
        help='Output path for raw response (default: PSTrax Example/department-status-report_<timestamp>.txt)',
    )
    args = parser.parse_args()

    sample_dir = Path(__file__).resolve().parent / 'PSTrax Example'
    sample_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out or str(
        sample_dir / f"department-status-report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    app = create_app()
    with app.app_context():
        result = perform_apparatus_scrape(save_raw_sample_path=out_path)
        print(result)
        if result and result.get('success'):
            print(f"Saved sample to {out_path}")
            return 0
        print(f"Capture incomplete. Raw response path (if written): {out_path}")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
