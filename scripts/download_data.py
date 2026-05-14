#!/usr/bin/env python3
"""
Download Market Data Script

Usage:
    python scripts/download_data.py --symbol sz000001 --freq day --start 20180101
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_feed.downloader import download_kdata, load_kdata
from data_feed.validator import validate_kdata, validate_hdf5_file


def main():
    parser = argparse.ArgumentParser(description="Download market data")
    parser.add_argument("--symbol", required=True, help="Stock symbol, e.g., sz000001")
    parser.add_argument("--freq", required=True, choices=["day", "week", "month", "min1", "min5", "min15", "min30", "min60"],
                        help="Data frequency")
    parser.add_argument("--start", required=True, help="Start date, YYYYMMDD")
    parser.add_argument("--end", help="End date, YYYYMMDD (optional)")
    parser.add_argument("--output", default="data/", help="Output directory")
    parser.add_argument("--validate", action="store_true", help="Validate data after download")
    parser.add_argument("--force", action="store_true", help="Force update (ignore incremental)")
    args = parser.parse_args()

    print(f"Downloading {args.symbol} {args.freq} from {args.start} to {args.end or 'now'}...")

    # 调用 downloader 下载数据
    hdf5_file = download_kdata(
        symbol=args.symbol,
        freq=args.freq,
        start=args.start,
        end=args.end,
        force_update=args.force
    )

    if hdf5_file is None:
        print("Download failed!")
        sys.exit(1)

    print(f"Download completed: {hdf5_file}")

    # 校验数据（可选）
    if args.validate:
        print("\nValidating data...")
        is_valid, issues = validate_hdf5_file(hdf5_file)
        if is_valid:
            print("✓ Data validation passed")
        else:
            print("✗ Data validation failed:")
            for issue in issues:
                print(f"  - {issue}")

    # 尝试加载并显示数据摘要
    print("\nLoading data summary...")
    data = load_kdata(args.symbol, args.freq)
    if data is not None:
        if hasattr(data, "__len__"):
            print(f"Total records: {len(data)}")
        print(f"Date range: {data.iloc[0]['datetime']} to {data.iloc[-1]['datetime']}")


if __name__ == "__main__":
    main()
