"""
KData Validator Module
校验 K 线数据的完整性和正确性
"""

from datetime import datetime, timedelta
from typing import Tuple, List, Optional

import pandas as pd


def validate_kdata(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    校验 KData DataFrame 的完整性和正确性

    Args:
        df: DataFrame with columns: datetime, open, high, low, close, volume

    Returns:
        (is_valid: bool, issues: list[str])
    """
    issues = []

    if df is None or len(df) == 0:
        return False, ["DataFrame is empty or None"]

    # 1. 检查必要的列
    required_cols = ["datetime", "open", "high", "low", "close", "volume"]
    for col in required_cols:
        if col not in df.columns:
            issues.append(f"Missing required column: {col}")

    if issues:
        return False, issues

    # 2. 检查 close <= 0
    invalid_close = df[df["close"] <= 0]
    if len(invalid_close) > 0:
        issues.append(f"Found {len(invalid_close)} records with close <= 0")
        issues.append(f"  Invalid dates: {invalid_close['datetime'].tolist()[:5]}...")

    # 3. 检查 high < low
    invalid_hl = df[df["high"] < df["low"]]
    if len(invalid_hl) > 0:
        issues.append(f"Found {len(invalid_hl)} records with high < low")
        issues.append(f"  Invalid dates: {invalid_hl['datetime'].tolist()[:5]}...")

    # 4. 检查 open/close 是否在 [low, high] 范围内
    invalid_oc = df[(df["open"] > df["high"]) | (df["open"] < df["low"]) |
                    (df["close"] > df["high"]) | (df["close"] < df["low"])]
    if len(invalid_oc) > 0:
        issues.append(f"Found {len(invalid_oc)} records with open/close out of [low, high] range")
        issues.append(f"  Invalid dates: {invalid_oc['datetime'].tolist()[:5]}...")

    # 5. 检查 volume < 0
    invalid_vol = df[df["volume"] < 0]
    if len(invalid_vol) > 0:
        issues.append(f"Found {len(invalid_vol)} records with volume < 0")

    # 6. 检查缺失交易日（只对日线及以上频率有意义）
    if _is_daily_frequency(df):
        missing_dates = _check_missing_trading_days(df)
        if missing_dates:
            issues.append(f"Missing {len(missing_dates)} trading days")
            issues.append(f"  Sample missing dates: {missing_dates[:5]}...")

    # 7. 检查 NaN 值
    nan_cols = df.columns[df.isna().any()].tolist()
    if nan_cols:
        issues.append(f"Found NaN values in columns: {nan_cols}")

    # 8. 检查重复日期
    duplicate_dates = df[df.duplicated(subset=["datetime"], keep=False)]
    if len(duplicate_dates) > 0:
        issues.append(f"Found {len(duplicate_dates)} records with duplicate datetime")

    is_valid = len(issues) == 0
    return is_valid, issues


def _is_daily_frequency(df: pd.DataFrame) -> bool:
    """判断是否为日线及以上频率（通过日期间隔判断）"""
    if len(df) < 2:
        return False

    df_sorted = df.sort_values("datetime")
    dates = pd.to_datetime(df_sorted["datetime"])
    intervals = dates.diff().dropna()

    if len(intervals) == 0:
        return False

    # 如果平均间隔大于等于 1 天，认为是日线及以上频率
    avg_interval_days = intervals.mean().total_seconds() / 86400
    return avg_interval_days >= 1.0


def _check_missing_trading_days(df: pd.DataFrame, max_gap: int = 5) -> List[str]:
    """
    检查缺失的交易日

    Args:
        df: DataFrame with datetime column
        max_gap: 连续缺失超过此天数则报告

    Returns:
        缺失的交易日列表（字符串格式）
    """
    df_sorted = df.sort_values("datetime").copy()
    dates = pd.to_datetime(df_sorted["datetime"])

    missing = []
    for i in range(1, len(dates)):
        gap = (dates.iloc[i] - dates.iloc[i - 1]).days
        if gap > max_gap:
            # 报告这个间隔中的每一天（避免太多输出）
            for d in range(1, min(gap, 10)):
                missing_date = dates.iloc[i - 1] + timedelta(days=d)
                missing.append(missing_date.strftime("%Y-%m-%d"))

    return missing


def validate_hdf5_file(filepath: str) -> Tuple[bool, List[str]]:
    """
    校验 HDF5 文件中的 KData

    Args:
        filepath: HDF5 文件路径

    Returns:
        (is_valid: bool, issues: list[str])
    """
    if not filepath.endswith(".h5"):
        return False, ["File is not an HDF5 file"]

    try:
        df = pd.read_hdf(filepath, key="kdata")
        return validate_kdata(df)
    except FileNotFoundError:
        return False, [f"File not found: {filepath}"]
    except Exception as e:
        return False, [f"Failed to read HDF5 file: {e}"]


def fix_kdata(df: pd.DataFrame) -> pd.DataFrame:
    """
    尝试修复 KData 中的常见问题（不推荐用于实盘，仅用于研究）

    Args:
        df: 原始 DataFrame

    Returns:
        修复后的 DataFrame
    """
    df_fixed = df.copy()

    # 删除 close <= 0 的行
    df_fixed = df_fixed[df_fixed["close"] > 0]

    # 删除 high < low 的行
    df_fixed = df_fixed[df_fixed["high"] >= df_fixed["low"]]

    # 删除 volume < 0 的行
    df_fixed = df_fixed[df_fixed["volume"] >= 0]

    # 删除重复日期（保留最后一个）
    df_fixed = df_fixed.drop_duplicates(subset=["datetime"], keep="last")

    # 按日期排序
    df_fixed = df_fixed.sort_values("datetime").reset_index(drop=True)

    return df_fixed