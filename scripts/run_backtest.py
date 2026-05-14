#!/usr/bin/env python3
"""
Run Backtest Script
使用 hikyuu.SYS_Simple 执行回测 (当 hikyuu 不可用时使用纯 Python 模拟)

Usage:
    python scripts/run_backtest.py --strategy ma_cross --symbol sz000001 --config config/backtest.yaml
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

# 尝试导入 hikyuu
try:
    import hikyuu as hk
    HIKYUU_AVAILABLE = True
except ImportError:
    HIKYUU_AVAILABLE = False
    print("Warning: hikyuu not available, using mock mode")

# 尝试导入 pandas，失败不影响
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_kdata(symbol: str, config: dict):
    """
    加载 K 线数据

    Args:
        symbol: 股票代码
        config: 配置字典

    Returns:
        KData 对象 (hikyuu.KData 或 list)
    """
    data_dir = Path(__file__).parent.parent / "data"
    hdf5_file = data_dir / f"{symbol}_day.h5"

    if not hdf5_file.exists():
        raise FileNotFoundError(f"HDF5 file not found: {hdf5_file}")

    # 尝试加载 hikyuu KData
    if HIKYUU_AVAILABLE:
        try:
            market = "SZ" if symbol.startswith("sz") else "SH"
            stock = hk.Stock(market, symbol)
            kdata = hk.KData(stock)
            kdata.load(str(hdf5_file))
            return kdata
        except Exception as e:
            print(f"hikyuu load failed: {e}")

    # Fallback: 使用 pandas
    if PANDAS_AVAILABLE:
        return pd.read_hdf(hdf5_file, key="kdata")

    raise RuntimeError("No suitable data loader available")


def filter_kdata_by_date(kdata, start_date: str, end_date: str):
    """按日期过滤 KData"""
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = datetime.strptime(end_date, "%Y%m%d")

    if PANDAS_AVAILABLE and isinstance(kdata, pd.DataFrame):
        kdata = kdata.copy()
        kdata['datetime'] = pd.to_datetime(kdata['datetime'])
        kdata = kdata[(kdata['datetime'] >= start_dt) & (kdata['datetime'] <= end_dt)]
        return kdata.reset_index(drop=True)

    return kdata


def create_strategy(strategy_name: str, config: dict):
    """创建策略实例"""
    from src.strategies.factory import get_strategy

    if strategy_name == "ma_cross":
        from src.strategies.ma_cross import MACrossStrategy
        params = config.get("strategy", {}).get("ma_cross", {"fast_period": 5, "slow_period": 20})
        return MACrossStrategy(params)
    else:
        strategy_class = get_strategy(strategy_name)
        if strategy_class is None:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        params = config.get("strategy", {}).get(strategy_name, {})
        return strategy_class(params)


def run_backtest_mock(strategy, kdata, initial_cash=1000000, commission=0.0003, slippage=0.0001):
    """使用纯 Python 模拟回测"""

    class MockTM:
        def __init__(self, init_cash):
            self.init_cash = init_cash
            self.cash = init_cash
            self.position = 0
            self.equity = [init_cash]
            self.trades = []
            self.count = 0

        def buy(self, price, vol, dt):
            cost = price * vol * (1 + commission + slippage)
            if cost <= self.cash:
                self.cash -= cost
                self.position += vol
                self.trades.append({'action': 'BUY', 'price': price, 'vol': vol, 'dt': dt})
                self.count += 1

        def sell(self, price, vol, dt):
            if self.position >= vol:
                revenue = price * vol * (1 - commission - slippage)
                self.cash += revenue
                self.position -= vol
                self.trades.append({'action': 'SELL', 'price': price, 'vol': vol, 'dt': dt})
                self.count += 1

        def update(self, price):
            self.equity.append(self.cash + self.position * price)

        def finalBalance(self):
            return self.equity[-1]

        def equityCurve(self):
            return self.equity

        def tradeCount(self):
            return self.count

    class MockSystem:
        def __init__(self, tm, kdata, strategy):
            self._tm = tm
            self._kdata = kdata
            self._strategy = strategy
            self._datetime_list = []

        def run(self):
            if len(self._kdata) < 2:
                return

            for i in range(len(self._kdata)):
                row = self._kdata.iloc[i]
                price = row['close']
                dt = row['datetime']
                self._datetime_list.append(dt)

                history = self._kdata.iloc[:i+1]
                signal = self._strategy.get_signal(history)

                if signal == 1:
                    self._tm.buy(price, 100, dt)
                elif signal == -1:
                    if self._tm.position > 0:
                        self._tm.sell(price, self._tm.position, dt)

                self._tm.update(price)

        def datetime(self):
            return self._datetime_list

        def tm(self):
            return self._tm

    tm = MockTM(initial_cash)
    sys_obj = MockSystem(tm, kdata, strategy)
    sys_obj.run()
    return sys_obj


def run_backtest(
    strategy_name: str,
    symbol: str,
    config: dict
):
    """运行回测"""
    print(f"\n{'='*60}")
    print(f"  Running Backtest: {strategy_name} on {symbol}")
    print(f"{'='*60}\n")

    # 1. 加载数据
    print("[1/4] Loading KData...")
    kdata = load_kdata(symbol, config)
    print(f"  Loaded {len(kdata)} bars")

    # 2. 日期过滤
    print("[2/4] Filtering by date...")
    backtest_config = config.get("backtest", {})
    start_date = backtest_config.get("start_date", "20190101")
    end_date = backtest_config.get("end_date", "20231231")
    kdata = filter_kdata_by_date(kdata, start_date, end_date)
    print(f"  After filter: {len(kdata)} bars")

    # 3. 创建策略
    print("[3/4] Creating strategy...")
    strategy = create_strategy(strategy_name, config)
    print(f"  Strategy: {strategy_name}")
    print(f"  Params: {strategy.params}")

    # 4. 运行回测
    print("[4/4] Running backtest...")
    if HIKYUU_AVAILABLE:
        from src.backtest.engine import BacktestEngine
        engine = BacktestEngine(
            strategy=strategy,
            kdata=kdata,
            initial_cash=backtest_config.get("initial_cash", 1000000),
            commission=config.get("trading", {}).get("commission", 0.0003),
            slippage=config.get("trading", {}).get("slippage", 0.0001)
        )
        sys_obj = engine.run()
    else:
        sys_obj = run_backtest_mock(
            strategy=strategy,
            kdata=kdata,
            initial_cash=backtest_config.get("initial_cash", 1000000),
            commission=config.get("trading", {}).get("commission", 0.0003),
            slippage=config.get("trading", {}).get("slippage", 0.0001)
        )

    print("  Backtest completed!")
    return sys_obj


def generate_report(sys_obj, output_dir="results"):
    """生成回测报告"""
    tm = sys_obj.tm()

    # 提取指标
    final_equity = tm.finalBalance()
    initial_cash = tm.init_cash
    total_return = (final_equity - initial_cash) / initial_cash if initial_cash > 0 else 0

    # 日期范围
    datetime_list = sys_obj.datetime()
    if len(datetime_list) >= 2:
        days = (datetime_list[-1] - datetime_list[0]).days
        years = max(days / 365.0, 0.01)
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = 0

    # 最大回撤
    equity_curve = tm.equityCurve()
    max_drawdown = 0
    peak = equity_curve[0]
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

    # 夏普比率
    returns = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i-1] != 0:
            returns.append((equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1])

    if len(returns) >= 2:
        import numpy as np
        avg_ret = np.mean(returns)
        std_ret = np.std(returns)
        sharpe = (avg_ret * 252 - 0.03) / (std_ret * np.sqrt(252)) if std_ret > 0 else 0
    else:
        sharpe = 0

    trade_count = tm.tradeCount()
    profit = final_equity - initial_cash

    # 打印报告
    print("\n" + "=" * 60)
    print("           BACKTEST REPORT")
    print("=" * 60)
    print(f"| {'Metric':<30} | {'Value':>20} |")
    print("-" * 60)
    print(f"| {'Total Return':<30} | {total_return*100:>19.2f}% |")
    print(f"| {'Annual Return':<30} | {annual_return*100:>19.2f}% |")
    print(f"| {'Max Drawdown':<30} | {max_drawdown*100:>19.2f}% |")
    print(f"| {'Sharpe Ratio':<30} | {sharpe:>20.4f} |")
    print(f"| {'Trade Count':<30} | {trade_count:>20} |")
    print(f"| {'Final Equity':<30} | {final_equity:>20,.2f} |")
    print(f"| {'Initial Cash':<30} | {initial_cash:>20,.2f} |")
    print(f"| {'Profit':<30} | {profit:>20,.2f} |")
    print("=" * 60)

    # 保存报告
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    md_file = os.path.join(output_dir, f"backtest_report_{timestamp}.md")
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# Backtest Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Metrics\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Total Return | {total_return*100:.2f}% |\n")
        f.write(f"| Annual Return | {annual_return*100:.2f}% |\n")
        f.write(f"| Max Drawdown | {max_drawdown*100:.2f}% |\n")
        f.write(f"| Sharpe Ratio | {sharpe:.4f} |\n")
        f.write(f"| Trade Count | {trade_count} |\n")
        f.write(f"| Final Equity | {final_equity:,.2f} |\n")
        f.write(f"| Initial Cash | {initial_cash:,.2f} |\n")
        f.write(f"| Profit | {profit:,.2f} |\n")

    csv_file = os.path.join(output_dir, f"backtest_metrics_{timestamp}.csv")
    import csv
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'total_return', 'annual_return', 'max_drawdown', 'sharpe_ratio',
            'trade_count', 'final_equity', 'initial_cash', 'profit'
        ])
        writer.writeheader()
        writer.writerow({
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'trade_count': trade_count,
            'final_equity': final_equity,
            'initial_cash': initial_cash,
            'profit': profit
        })

    return md_file, csv_file


def main():
    parser = argparse.ArgumentParser(description="Run backtest for a strategy")
    parser.add_argument("--strategy", default="ma_cross", help="Strategy name")
    parser.add_argument("--symbol", default="sz000001", help="Stock symbol")
    parser.add_argument("--config", default="config/backtest.yaml", help="Backtest config file path")
    parser.add_argument("--output", default="results", help="Output directory for reports")
    parser.add_argument("--start", help="Start date (YYYYMMDD), overrides config")
    parser.add_argument("--end", help="End date (YYYYMMDD), overrides config")
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 覆盖日期范围
    if args.start:
        config.setdefault("backtest", {})["start_date"] = args.start
    if args.end:
        config.setdefault("backtest", {})["end_date"] = args.end

    output_dir = config.get("output", {}).get("result_dir", args.output)

    try:
        sys_obj = run_backtest(args.strategy, args.symbol, config)

        print("\n" + "="*60)
        print("  Backtest Results")
        print("="*60)

        md_file, csv_file = generate_report(sys_obj, output_dir)

        print(f"\nReports saved to:")
        print(f"  - {md_file}")
        print(f"  - {csv_file}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
