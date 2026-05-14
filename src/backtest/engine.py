"""
Backtest Engine Module
使用 hikyuu.SYS_Simple 构建回测系统
当 hikyuu 不可用时，使用纯 Python 模拟实现
"""

from typing import Optional, List
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 尝试导入 hikyuu
try:
    import hikyuu as hk
    HIKYUU_AVAILABLE = True
except ImportError:
    HIKYUU_AVAILABLE = False
    print("Warning: hikyuu not available, using mock backtest engine")

from src.strategies.base_strategy import BaseStrategy


class MockTradeManager:
    """模拟交易管理器"""

    def __init__(self, initial_cash: float, commission: float = 0.0003, slippage: float = 0.0001):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission = commission
        self.slippage = slippage
        self.position = 0  # 持仓股数
        self.equity_curve = [initial_cash]
        self.trades = []
        self.trade_count = 0

    def buy(self, price: float, volume: int, datetime: datetime):
        """买入"""
        cost = price * volume * (1 + self.commission + self.slippage)
        if cost <= self.cash:
            self.cash -= cost
            self.position += volume
            self.trades.append({
                'action': 'BUY',
                'price': price,
                'volume': volume,
                'datetime': datetime,
                'cost': cost
            })
            self.trade_count += 1

    def sell(self, price: float, volume: int, datetime: datetime):
        """卖出"""
        if self.position >= volume:
            revenue = price * volume * (1 - self.commission - self.slippage)
            self.cash += revenue
            self.position -= volume
            self.trades.append({
                'action': 'SELL',
                'price': price,
                'volume': volume,
                'datetime': datetime,
                'revenue': revenue
            })
            self.trade_count += 1

    def update_equity(self, current_price: float):
        """更新权益"""
        total_value = self.cash + self.position * current_price
        self.equity_curve.append(total_value)

    def final_balance(self) -> float:
        """最终权益"""
        return self.equity_curve[-1] if self.equity_curve else self.initial_cash

    def equity_curve(self) -> List[float]:
        """权益曲线"""
        return self.equity_curve


class MockSystem:
    """模拟回测系统"""

    def __init__(self, tm: MockTradeManager, kdata: pd.DataFrame, strategy: BaseStrategy):
        self.tm = tm
        self.kdata = kdata
        self.strategy = strategy
        self._datetime_list = []

    def run(self):
        """执行回测"""
        if len(self.kdata) < 2:
            return

        # 按日期排序
        df = self.kdata.sort_values('datetime').reset_index(drop=True)

        for i in range(len(df)):
            row = df.iloc[i]
            current_price = row['close']
            current_dt = row['datetime']

            self._datetime_list.append(current_dt)

            # 获取信号
            history = df.iloc[:i+1]
            signal = self.strategy.get_signal(history)

            # 执行交易
            if signal == 1:  # 买入信号
                # 每次买入 100 股
                volume = 100
                self.tm.buy(current_price, volume, current_dt)
            elif signal == -1:  # 卖出信号
                # 卖出全部持仓
                volume = self.tm.position
                if volume > 0:
                    self.tm.sell(current_price, volume, current_dt)

            # 更新权益
            self.tm.update_equity(current_price)

    def datetime(self) -> List[datetime]:
        """获取日期列表"""
        return self._datetime_list

    def tm(self):
        """获取交易管理器"""
        return self.tm


class BacktestEngine:
    """回测引擎封装"""

    def __init__(
        self,
        strategy: BaseStrategy,
        kdata,
        initial_cash: float = 1000000.0,
        commission: float = 0.0003,
        slippage: float = 0.0001
    ):
        """
        初始化回测引擎

        Args:
            strategy: 策略实例
            kdata: K线数据 (hikyuu.KData 或 pandas.DataFrame)
            initial_cash: 初始资金
            commission: 手续费率
            slippage: 滑点
        """
        self.strategy = strategy
        self.kdata = kdata
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage
        self._sys = None

    def run(self):
        """
        运行回测，返回 sys 对象

        Returns:
            hikyuu.SYS_Simple 或 MockSystem 对象
        """
        if HIKYUU_AVAILABLE:
            return self._run_hikyuu()
        else:
            return self._run_mock()

    def _run_hikyuu(self):
        """使用 hikyuu 运行回测"""
        # 创建交易系统
        tm = hk.crtTM(
            self.initial_cash,          # 初始资金
            hk.PRICE_EQUITY,            # 权益模式
            hk.CDT_EQUITY,              # 现金模式
            self.commission,            # 手续费
            self.slippage               # 滑点
        )

        # 创建信号指示器 (绑定策略)
        signal = hk.SG_Fixed(self.strategy.get_signal)

        # 创建资金管理
        money_manager = hk.MM_FixedCount(100)  # 每次固定买100股

        # 创建系统
        self._sys = hk.SYS_Simple(
            tm=tm,
            sg=signal,
            mm=money_manager
        )

        # 设置数据
        if isinstance(self.kdata, hk.KData):
            self._sys.setKData(self.kdata)
        else:
            raise ValueError("kdata must be hikyuu KData object")

        # 执行回测
        self._sys.run()
        return self._sys

    def _run_mock(self):
        """使用纯 Python 模拟回测"""
        # 转换 kdata 为 DataFrame
        if hasattr(self.kdata, 'to_pandas'):
            # hikyuu KData 转换
            df = pd.DataFrame({
                'datetime': [dt for dt in self.kdata.datetime()],
                'open': self.kdata.open(),
                'high': self.kdata.high(),
                'low': self.kdata.low(),
                'close': self.kdata.close(),
                'volume': self.kdata.volume()
            })
        elif isinstance(self.kdata, pd.DataFrame):
            df = self.kdata.copy()
        else:
            raise ValueError("kdata must be hikyuu KData or pandas DataFrame")

        # 创建模拟交易管理器和系统
        tm = MockTradeManager(self.initial_cash, self.commission, self.slippage)
        self._sys = MockSystem(tm, df, self.strategy)
        self._sys.run()
        return self._sys

    @property
    def system(self):
        """获取系统对象"""
        return self._sys

    @property
    def tm(self):
        """获取交易管理器"""
        if self._sys:
            return self._sys.tm()
        return None


def create_engine(
    strategy: BaseStrategy,
    kdata,
    config: dict = None
) -> BacktestEngine:
    """
    工厂函数：创建回测引擎

    Args:
        strategy: 策略实例
        kdata: K线数据
        config: 配置字典

    Returns:
        BacktestEngine 实例
    """
    if config is None:
        config = {}

    return BacktestEngine(
        strategy=strategy,
        kdata=kdata,
        initial_cash=config.get("initial_cash", 1000000.0),
        commission=config.get("commission", 0.0003),
        slippage=config.get("slippage", 0.0001)
    )


def load_kdata_from_hdf5(symbol: str, freq: str = "day") -> Optional:
    """
    从 HDF5 文件加载 KData

    Args:
        symbol: 股票代码
        freq: 频率

    Returns:
        pandas.DataFrame (hikyuu 不可用时) 或 hk.KData (hikyuu 可用时)
    """
    data_dir = Path(__file__).parent.parent.parent / "data"
    hdf5_file = data_dir / f"{symbol}_{freq}.h5"

    if not hdf5_file.exists():
        return None

    if HIKYUU_AVAILABLE:
        try:
            market = "SZ" if symbol.startswith("sz") else "SH"
            stock = hk.Stock(market, symbol)
            kdata = hk.KData(stock)
            kdata.load(str(hdf5_file))
            return kdata
        except Exception as e:
            print(f"Failed to load with hikyuu: {e}")

    # Fallback to pandas
    try:
        return pd.read_hdf(hdf5_file, key="kdata")
    except Exception as e:
        print(f"Failed to load kdata: {e}")
        return None