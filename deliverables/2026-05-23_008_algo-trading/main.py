"""
AI Studio Accademia Milano — Algo Trading Bot
SMA Crossover Strategy, Alpaca Paper Trading

DISCLAIMER: This software does not constitute regulated financial advice.
It is based on AI knowledge and general business principles. Use only with
Alpaca paper trading accounts. Do not risk real capital without fully
understanding the strategy and its risks. AI Studio accepts no liability.
"""
import argparse
import os
import sys

from trader import run_strategy

DISCLAIMER = """
⚠  DISCLAIMER: This software does not constitute regulated financial advice.
    It is based on AI knowledge and general business principles.
    Paper trading only. Real-money trading requires your own due diligence.
"""

DEFAULT_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]


def main():
    parser = argparse.ArgumentParser(description="SMA Crossover Algo Bot — Alpaca Paper")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument(
        "--live", action="store_true", help="Execute paper orders (default: dry run)"
    )
    parser.add_argument("--short", type=int, default=20, help="Short SMA window")
    parser.add_argument("--long", type=int, default=50, help="Long SMA window")
    args = parser.parse_args()

    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        print("Error: set ALPACA_API_KEY and ALPACA_SECRET_KEY as environment variables.")
        sys.exit(1)

    print(DISCLAIMER)
    print(f"Strategy : SMA {args.short}/{args.long} crossover")
    print(f"Mode     : {'EXECUTE (paper)' if args.live else 'DRY RUN (signals only)'}")
    print(f"Symbols  : {', '.join(args.symbols)}")
    print()
    print(f"{'Symbol':<8} {'Signal':<8} {'RSI':>6}  Action")
    print("-" * 60)

    results = run_strategy(
        api_key, secret_key, args.symbols,
        dry_run=not args.live,
        short_window=args.short,
        long_window=args.long,
    )
    for r in results:
        rsi_str = f"{r['rsi']:>5.1f}" if r["rsi"] is not None else "  N/A"
        print(f"{r['symbol']:<8} {r['signal']:<8} {rsi_str}  {r['action']}")


if __name__ == "__main__":
    main()
