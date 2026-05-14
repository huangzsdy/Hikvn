"""
Backtest Reporter Module
从 sys.tm() 提取回测指标并输出报告
"""

import os
from datetime import datetime
from typing import Optional
import csv


def calculate_sharpe_ratio(returns: list, risk_free_rate: float = 0.03) -> float:
    """
    计算夏普比率

    Args:
        returns: 收益率列表
        risk_free_rate: 无风险利率 (年化)

    Returns:
        夏普比率
    """
    if not returns or len(returns) < 2:
        return 0.0

    import numpy as np
    returns = np.array(returns)

    # 年化收益率
    avg_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return 0.0

    # 假设一年252个交易日
    sharpe = (avg_return * 252 - risk_free_rate) / (std_return * np.sqrt(252))
    return sharpe


class BacktestReporter:
    """回测报告生成器"""

    def __init__(self, sys_obj):
        """
        初始化报告生成器

        Args:
            sys_obj: hikyuu.SYS_Simple 对象
        """
        self.sys = sys_obj
        self.tm = sys.tm() if sys else None

    def get_metrics(self) -> dict:
        """
        从交易管理器提取回测指标

        Returns:
            指标字典
        """
        if self.tm is None:
            return {}

        try:
            # 总收益 = 最终权益 - 初始资金
            final_equity = self.tm.finalBalance()
            initial_cash = self.tm.initCash()

            total_return = (final_equity - initial_cash) / initial_cash if initial_cash > 0 else 0

            # 年化收益
            datetime_list = self.sys.datetime()
            if len(datetime_list) >= 2:
                start_date = datetime_list[0]
                end_date = datetime_list[-1]
                days = (end_date - start_date).days
                years = days / 365.0 if days > 0 else 1
                annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
            else:
                annual_return = 0

            # 最大回撤
            equity_curve = self.tm.equityCurve()
            if hasattr(equity_curve, '__len__') and len(equity_curve) > 0:
                max_drawdown = self._calculate_max_drawdown(equity_curve)
            else:
                max_drawdown = 0

            # 收益序列用于计算夏普
            returns = self._calculate_returns(equity_curve)
            sharpe = calculate_sharpe_ratio(returns)

            # 交易次数
            trade_count = self.tm.tradeCount() if hasattr(self.tm, 'tradeCount') else 0

            return {
                "total_return": total_return,
                "annual_return": annual_return,
                "max_drawdown": max_drawdown,
                "sharpe_ratio": sharpe,
                "trade_count": trade_count,
                "final_equity": final_equity,
                "initial_cash": initial_cash,
                "profit": final_equity - initial_cash
            }
        except Exception as e:
            print(f"Error extracting metrics: {e}")
            return {}

    def _calculate_max_drawdown(self, equity_curve: list) -> float:
        """计算最大回撤"""
        if not equity_curve:
            return 0.0

        max_dd = 0.0
        peak = equity_curve[0]

        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _calculate_returns(self, equity_curve: list) -> list:
        """计算收益率序列"""
        if not equity_curve or len(equity_curve) < 2:
            return []

        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] != 0:
                ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
                returns.append(ret)
        return returns

    def print_report(self):
        """打印 Markdown 格式报告"""
        metrics = self.get_metrics()

        if not metrics:
            print("No metrics available")
            return

        print("\n" + "=" * 60)
        print("           BACKTEST REPORT")
        print("=" * 60)
        print(f"| {'Metric':<30} | {'Value':>20} |")
        print("-" * 60)
        print(f"| {'Total Return':<30} | {metrics['total_return']*100:>19.2f}% |")
        print(f"| {'Annual Return':<30} | {metrics['annual_return']*100:>19.2f}% |")
        print(f"| {'Max Drawdown':<30} | {metrics['max_drawdown']*100:>19.2f}% |")
        print(f"| {'Sharpe Ratio':<30} | {metrics['sharpe_ratio']:>20.4f} |")
        print(f"| {'Trade Count':<30} | {metrics['trade_count']:>20} |")
        print(f"| {'Final Equity':<30} | {metrics['final_equity']:>20,.2f} |")
        print(f"| {'Initial Cash':<30} | {metrics['initial_cash']:>20,.2f} |")
        print(f"| {'Profit':<30} | {metrics['profit']:>20,.2f} |")
        print("=" * 60)

    def save_report(self, output_dir: str = "results"):
        """
        保存报告到 Markdown 和 CSV 文件

        Args:
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)

        metrics = self.get_metrics()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Markdown 报告
        md_file = os.path.join(output_dir, f"backtest_report_{timestamp}.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write("# Backtest Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Metrics\n\n")
            f.write("| Metric | Value |\n")
            f.write("|--------|-------|\n")
            for key, value in metrics.items():
                if isinstance(value, float):
                    if key in ['total_return', 'annual_return', 'max_drawdown']:
                        f.write(f"| {key} | {value*100:.2f}% |\n")
                    else:
                        f.write(f"| {key} | {value:.4f} |\n")
                else:
                    f.write(f"| {key} | {value} |\n")
            f.write("\n## Summary\n\n")
            f.write(f"- Total Return: {metrics.get('total_return', 0)*100:.2f}%\n")
            f.write(f"- Annual Return: {metrics.get('annual_return', 0)*100:.2f}%\n")
            f.write(f"- Max Drawdown: {metrics.get('max_drawdown', 0)*100:.2f}%\n")
            f.write(f"- Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.4f}\n")

        print(f"Report saved to {md_file}")

        # CSV 文件
        csv_file = os.path.join(output_dir, f"backtest_metrics_{timestamp}.csv")
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=metrics.keys())
            writer.writeheader()
            writer.writerow(metrics)

        print(f"CSV saved to {csv_file}")

        return md_file, csv_file


def generate_report(sys_obj, output_dir: str = "results") -> tuple:
    """
    生成回测报告的便捷函数

    Args:
        sys_obj: hikyuu.SYS_Simple 对象
        output_dir: 输出目录

    Returns:
        (markdown_file, csv_file)
    """
    reporter = BacktestReporter(sys_obj)
    reporter.print_report()
    return reporter.save_report(output_dir)