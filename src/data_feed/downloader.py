"""
KData Downloader Module
使用 tushare pro_bar 获取数据，fallback 到 akshare
转换为 Hikyuu KData 并保存为 HDF5
支持增量更新
"""

import os
from datetime import datetime
from typing import Optional

import pandas as pd

# 尝试导入 hikyuu
try:
    import hikyuu as hk
    HIKYUU_AVAILABLE = True
except ImportError:
    HIKYUU_AVAILABLE = False
    print("Warning: hikyuu not available, will use pandas only")

# 尝试导入 tushare
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

# akshare
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False


# 频率映射
FREQ_MAP = {
    "day": "D",
    "week": "W",
    "month": "M",
    "min1": "1m",
    "min5": "5m",
    "min15": "15m",
    "min30": "30m",
    "min60": "60m",
}


def _get_token() -> Optional[str]:
    """从环境变量获取 tushare token"""
    token = os.getenv("TS_TOKEN")
    if not token:
        # 尝试从 .env 文件加载
        from dotenv import load_dotenv
        load_dotenv()
        token = os.getenv("TS_TOKEN")
    return token


def _detect_market(symbol: str) -> str:
    """检测市场前缀"""
    symbol = symbol.lower()
    if symbol.startswith("sz"):
        return "SZ"
    elif symbol.startswith("sh"):
        return "SH"
    elif symbol.startswith("bj"):
        return "BJ"
    elif symbol.startswith("hk"):
        return "HK"
    else:
        # 默认尝试深交所
        return "SZ"


def _parse_date(date_str: str) -> str:
    """解析日期字符串为 YYYYMMDD 格式"""
    if isinstance(date_str, int):
        return str(date_str)
    # 尝试解析各种格式
    for fmt in ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"]:
        try:
            dt = datetime.strptime(str(date_str), fmt)
            return dt.strftime("%Y%m%d")
        except ValueError:
            continue
    return str(date_str)


def _hdf5_path(symbol: str, freq: str) -> str:
    """生成 HDF5 文件路径"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, f"{symbol}_{freq}.h5")


def _get_latest_date(symbol: str, freq: str) -> Optional[str]:
    """获取本地 HDF5 文件的最新日期"""
    hdf5_file = _hdf5_path(symbol, freq)
    if not os.path.exists(hdf5_file):
        return None

    try:
        if HIKYUU_AVAILABLE:
            kdata = hk.KData()
            kdata.load(hdf5_file)
            if len(kdata) > 0:
                return kdata.datetime[-1].strftime("%Y%m%d")
        else:
            # 使用 pandas 读取
            df = pd.read_hdf(hdf5_file, key="kdata")
            if len(df) > 0:
                return df["datetime"].iloc[-1].strftime("%Y%m%d")
    except Exception:
        pass
    return None


def download_via_tushare(
    symbol: str,
    freq: str = "day",
    start: str = "20180101",
    end: str = None,
    adjust: str = "qfq"
) -> Optional[pd.DataFrame]:
    """
    通过 tushare pro_bar 下载数据

    Args:
        symbol: 股票代码，如 sz000001
        freq: K 线频率 (day/week/month/min1/min5)
        start: 开始日期 YYYYMMDD
        end: 结束日期 YYYYMMDD
        adjust: 复权方式 (qfq/bfq/hfq)

    Returns:
        DataFrame with columns: datetime, open, high, low, close, volume
    """
    if not TUSHARE_AVAILABLE:
        return None

    token = _get_token()
    if not token:
        print("Warning: TS_TOKEN not set, cannot use tushare")
        return None

    try:
        ts.set_token(token)
        pro = ts.pro_api()

        # 转换代码格式
        ts_code = symbol
        if symbol.startswith("sz"):
            ts_code = symbol[2:] + ".SZ"
        elif symbol.startswith("sh"):
            ts_code = symbol[2:] + ".SH"
        elif symbol.startswith("bj"):
            ts_code = symbol[2:] + ".BJ"

        # tushare 频率映射
        ts_freq_map = {
            "day": "D",
            "week": "W",
            "month": "M",
            "min1": "1min",
            "min5": "5min",
            "min15": "15min",
            "min30": "30min",
            "min60": "60min",
        }
        api_freq = ts_freq_map.get(freq, "D")

        # 日期范围
        start_date = _parse_date(start)
        end_date = _parse_date(end) if end else datetime.now().strftime("%Y%m%d")

        # 增量更新：检测本地最新日期
        latest_local = _get_latest_date(symbol, freq)
        if latest_local and latest_local >= start_date:
            start_date = latest_local  # 从本地最新日期之后开始下载

        df = pro.security_daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        ) if freq == "day" else None

        if df is None and freq in ["min1", "min5", "min15", "min30", "min60"]:
            # tushare 分钟后需要用 futu 或其他接口，这里先用 demo 数据
            print(f"tushare minute data not fully supported for {freq}, will try akshare")
            return None

        if df is not None and len(df) > 0:
            df = df.rename(columns={
                "trade_date": "datetime",
                "vol": "volume"
            })
            df["datetime"] = pd.to_datetime(df["datetime"])
            return df[["datetime", "open", "high", "low", "close", "volume"]]

    except Exception as e:
        print(f"tushare download failed: {e}")

    return None


def download_via_akshare(
    symbol: str,
    freq: str = "day",
    start: str = "20180101",
    end: str = None
) -> Optional[pd.DataFrame]:
    """
    通过 akshare 下载数据作为 fallback

    Args:
        symbol: 股票代码
        freq: K 线频率
        start: 开始日期
        end: 结束日期

    Returns:
        DataFrame with columns: datetime, open, high, low, close, volume
    """
    if not AKSHARE_AVAILABLE:
        return None

    try:
        start_date = _parse_date(start)
        end_date = _parse_date(end) if end else datetime.now().strftime("%Y%m%d")

        # 增量更新
        latest_local = _get_latest_date(symbol, freq)
        if latest_local and latest_local >= start_date:
            start_date = latest_local

        # 转换代码格式 for akshare
        akshare_symbol = symbol
        if symbol.startswith("sz"):
            akshare_symbol = symbol[2:]
        elif symbol.startswith("sh"):
            akshare_symbol = symbol[2:]

        df = None
        if freq == "day":
            df = ak.stock_zh_a_hist(
                symbol=akshare_symbol,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
        elif freq in ["min1", "min5", "min15", "min30", "min60"]:
            period = freq.replace("min", "")
            df = ak.stock_zh_a_hist_min(
                symbol=akshare_symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
                adjust="qfq"
            )

        if df is not None and len(df) > 0:
            # 统一列名
            df = df.rename(columns={
                "日期": "datetime",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume"
            })
            df["datetime"] = pd.to_datetime(df["datetime"])
            return df[["datetime", "open", "high", "low", "close", "volume"]]

    except Exception as e:
        print(f"akshare download failed: {e}")

    return None


def convert_to_hikyuu_kdata(df: pd.DataFrame, symbol: str, freq: str) -> Optional:
    """
    将 pandas DataFrame 转换为 Hikyuu KData

    Args:
        df: DataFrame with datetime, open, high, low, close, volume
        symbol: 股票代码
        freq: K 线频率

    Returns:
        hk.KData object or None if hikyuu not available
    """
    if not HIKYUU_AVAILABLE:
        return None

    try:
        market = _detect_market(symbol)
        stock = hk.Stock(market, symbol)

        # 创建 KData 对象
        kdata = hk.KData(stock, hk.get_nano_time_by_datetime(df["datetime"].iloc[0]))

        # 填充数据
        for _, row in df.iterrows():
            kdata.push(
                hk.KRecord(
                    datetime=hk.get_nano_time_by_datetime(row["datetime"]),
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"]
                )
            )

        return kdata
    except Exception as e:
        print(f"Failed to convert to hikyuu KData: {e}")
        return None


def save_to_hdf5(df: pd.DataFrame, symbol: str, freq: str) -> str:
    """
    保存 DataFrame 到 HDF5 文件

    Args:
        df: DataFrame to save
        symbol: 股票代码
        freq: K 线频率

    Returns:
        文件路径
    """
    hdf5_file = _hdf5_path(symbol, freq)

    # 使用 pandas 保存，确保目录存在
    os.makedirs(os.path.dirname(hdf5_file), exist_ok=True)

    # 如果文件已存在，则合并数据
    if os.path.exists(hdf5_file):
        try:
            existing_df = pd.read_hdf(hdf5_file, key="kdata")
            # 合并并去重
            combined = pd.concat([existing_df, df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["datetime"], keep="last")
            combined = combined.sort_values("datetime")
            combined.to_hdf(hdf5_file, key="kdata", mode="w")
        except Exception:
            # 如果合并失败，直接覆盖
            df.to_hdf(hdf5_file, key="kdata", mode="w")
    else:
        df.to_hdf(hdf5_file, key="kdata", mode="w")

    return hdf5_file


def download_kdata(
    symbol: str,
    freq: str = "day",
    start: str = "20180101",
    end: str = None,
    force_update: bool = False
) -> Optional[str]:
    """
    下载 K 线数据主函数

    Args:
        symbol: 股票代码，如 sz000001
        freq: K 线频率 (day/week/month/min1/min5 等)
        start: 开始日期 YYYYMMDD
        end: 结束日期 YYYYMMDD
        force_update: 是否强制更新（忽略增量检测）

    Returns:
        HDF5 文件路径，失败返回 None
    """
    print(f"Downloading {symbol} {freq} from {start} to {end or 'now'}...")

    df = None

    # 尝试 tushare
    if not force_update:
        df = download_via_tushare(symbol, freq, start, end)

    # fallback 到 akshare
    if df is None:
        print("tushare failed, trying akshare...")
        df = download_via_akshare(symbol, freq, start, end)

    if df is None or len(df) == 0:
        print(f"No data retrieved for {symbol}")
        return None

    print(f"Retrieved {len(df)} records")

    # 保存到 HDF5
    hdf5_file = save_to_hdf5(df, symbol, freq)
    print(f"Saved to {hdf5_file}")

    return hdf5_file


# 便捷函数：直接加载为 Hikyuu KData
def load_kdata(symbol: str, freq: str = "day") -> Optional:
    """
    从 HDF5 加载 KData

    Args:
        symbol: 股票代码
        freq: K 线频率

    Returns:
        hk.KData object or pandas DataFrame (if hikyuu not available)
    """
    hdf5_file = _hdf5_path(symbol, freq)

    if not os.path.exists(hdf5_file):
        return None

    if HIKYUU_AVAILABLE:
        return hk.KData()
        # 注意：hikyuu 的 load 方法可能不同，这里需要根据实际情况调整
        # return kdata.load(hdf5_file)
    else:
        return pd.read_hdf(hdf5_file, key="kdata")