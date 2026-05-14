# Roo Code System Instructions — Quant Project (Hikyuu + vn.py)

> 🤖 Roo Code：每次对话开始时完整读取本文件，严格遵照其中的技术栈、目录约定和编码规范执行任务。
> 如遇模糊需求先问用户，不要擅自假设。

## 项目概述
基于 Hikyuu Quant Framework (C++/Python) 做回测与策略研究，
可选集成 VeighNa (vn.py) 作为实盘交易网关层。
Python >= 3.10，推荐使用 virtualenv 或 conda。

## 技术栈
- 回测引擎: hikyuu (pip install hikyuu)
- 实盘网关(可选): vnpy, vnpy_ctp, vnpy_xtp
- 数据源: tushare_pro (token 存 .env TS_TOKEN), akshare 兜底
- 数据库: SQLite 本地存储行情元数据; 可选 TDengine/ClickHouse
- 指标计算: hikyuu 内置 + TA-Lib + 自定义 Python/C++ 扩展
- 日志: loguru，日志写到 logs/
- 配置: YAML (config/ 目录), 敏感信息通过 python-dotenv 加载

## 目录约定（严格遵循）
- src/strategies/ 下每个策略一个文件，继承 src/strategies/base_strategy.py
- 所有硬编码参数放到 config/strategy_params.yaml，代码中用 yaml 加载
- 回测结果输出到 results/{strategy_name}_{YYYYMMDD}/
- 禁止在业务代码中写死 API Token 或数据库密码

## 常用开发命令
- 安装依赖: pip install -r requirements.txt
- 下载数据: python scripts/download_data.py --symbol sz000001 --freq day --start 20180101
- 运行回测: python scripts/run_backtest.py --strategy ma_cross --config config/backtest.yaml
- 参数优化: python scripts/optimize.py --strategy ma_cross --param-grid config/ma_cross_grid.yaml
- 跑测试: pytest tests/ -v

## 代码规范
- Python: PEP8, 类型注解, docstring NumPy 风格
- 策略类必须实现: `get_signal(self, kdata) -> int` (+1买/-1卖/0观望)
- 所有异常必须被捕获并记录，不允许裸 except: pass
- git commit message 格式: feat(strategy)|fix(data)|refactor(backtest): 简述

## 特别约束（AI 必须遵守）
1. 不要从零实现回测引擎，必须使用 hikyuu.SYS_Simple / hikyuu.crtTM
2. 新策略只需继承 base_strategy.py，在 factory.py 注册，不得修改其他已有策略文件
3. 每次修改后若影响功能，自动运行相关 pytest
4. 遇到不明确需求先问我再写代码
5. 解释型代码