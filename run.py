"""量化智能体 CLI 入口。

用法示例：
    python run.py backtest --symbol AAPL --strategy ma_cross --days 500
    python run.py serve                 # 启动网页看板 http://127.0.0.1:8000
    python run.py agent --offline       # 离线演示自动交易（合成行情）
"""
from __future__ import annotations

import argparse
import sys

from quant.config import load_config
from quant.data.feed import get_feed
from quant.strategy.base import get_strategy


def cmd_backtest(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    feed = get_feed(cfg["data"]["feed"] if not args.offline else "synthetic")
    bars = feed.get_bars(args.symbol, days=args.days)
    strat = get_strategy(args.strategy, cfg["strategy"].get("params") or {})
    from quant.backtest import run_backtest

    result = run_backtest(
        bars,
        strat,
        initial_cash=args.cash,
        commission=float(cfg["portfolio"]["commission"]),
        stop_loss_pct=args.stop_loss if args.stop_loss >= 0 else float(cfg["risk"]["stop_loss_pct"]),
        max_position_pct=float(cfg["risk"]["max_position_pct"]),
    )
    m = result.metrics
    print(f"\n=== 回测结果: {args.symbol} / {args.strategy} ===")
    print(f"初始资金      : {args.cash:,.2f}")
    print(f"期末权益      : {m['final_equity']:,.2f}")
    print(f"总收益率      : {m['total_return']:.2%}")
    print(f"年化收益率    : {m['annualized_return']:.2%}")
    print(f"最大回撤      : {m['max_drawdown']:.2%}")
    print(f"夏普比率      : {m['sharpe']:.2f}")
    print(f"胜率          : {m['win_rate']:.2%}  (平仓 {m['num_trades']} 笔)")
    print(f"累计盈亏      : {m['total_pnl']:+,.2f}   买入持有基准: {m['buyhold_return']:.2%}\n")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    cfg = load_config(args.config)
    from quant.api.server import create_app

    host, port = cfg["api"]["host"], int(cfg["api"]["port"])
    print(f"看板已启动: http://{host}:{port}  (Ctrl+C 退出)")
    uvicorn.run(create_app(cfg), host=host, port=port, reload=False)
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    if args.offline:
        cfg["data"]["feed"] = "synthetic"
    from quant.agent import LiveAgent

    agent = LiveAgent(cfg)
    agent.start()
    print(f"自动交易已启动（模拟盘, {agent.interval:.0f}s 轮询, 标的: {agent.symbols}）Ctrl+C 停止")
    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
        print("\n已停止。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="quant-agent", description="量化智能体")
    parser.add_argument("--config", default=None, help="配置文件路径（默认 config.yaml）")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    p_bt = sub.add_parser("backtest", parents=[common], help="运行历史回测")
    p_bt.add_argument("--symbol", default="AAPL")
    p_bt.add_argument("--strategy", default="ma_cross", choices=["ma_cross", "rsi"])
    p_bt.add_argument("--days", type=int, default=500)
    p_bt.add_argument("--cash", type=float, default=10000.0)
    p_bt.add_argument("--stop-loss", type=float, default=-1.0, help="自定义止损比例, -1 用配置")
    p_bt.add_argument("--offline", action="store_true", help="用离线合成行情")
    p_bt.set_defaults(func=cmd_backtest)

    p_sv = sub.add_parser("serve", parents=[common], help="启动网页看板")
    p_sv.set_defaults(func=cmd_serve)

    p_ag = sub.add_parser("agent", parents=[common], help="启动自动交易(模拟盘)")
    p_ag.add_argument("--offline", action="store_true", help="用离线合成行情演示")
    p_ag.set_defaults(func=cmd_agent)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
