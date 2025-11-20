# run_backtest.py

import json
import matplotlib.pyplot as plt

from src.backtester import Backtester, WeightedStrategy
from src.price_manager import PriceManager
from src.execution_manager import ExecutionManager
from src.order_manager import OrderManager
from src.position_manager import PositionManager
from src import strategies as strat_mod  # we will use this to look up classes

CONFIG_PATH = "src/settings/market_data_config.json"
STRATEGY_CONFIG_PATH = "src/settings/strategy_config.json"
EXEC_SETTINGS_PATH = "src/settings/execution_settings.json"
INITIAL_PORTFOLIO_PATH = "src/settings/initial_positions.json"


def build_strategies_from_json(pm: PriceManager) -> dict:
    """
    Build strategies_by_symbol from settings/strategy_config.json

    JSON schema:
      {
        "TICKER": [
          {
            "class": "MomentumStrategy",
            "weight": 1.0,
            "params": { ... }
          },
          ...
        ],
        ...
      }
    """
    with open(STRATEGY_CONFIG_PATH, "r") as f:
        cfg = json.load(f)

    strategies_by_symbol: dict = {}

    for symbol, strat_list in cfg.items():
        strategies_by_symbol[symbol] = []

        for entry in strat_list:
            class_name = entry["class"]
            weight = entry.get("weight", 1.0)
            params = entry.get("params", {})

            # Look up the class on strategies module
            cls = getattr(strat_mod, class_name, None)
            if cls is None:
                raise ValueError(f"Strategy class '{class_name}' not found in src.strategies")

            # Every strategy in your file has signature (price_manager, symbol, ...)
            strategy_instance = cls(price_manager=pm, symbol=symbol, **params)

            strategies_by_symbol[symbol].append(
                WeightedStrategy(strategy=strategy_instance, weight=weight)
            )

    return strategies_by_symbol


def main():
    pmgr = PositionManager.from_json(INITIAL_PORTFOLIO_PATH)
    pm = PriceManager(max_history=200)

    strategies_by_symbol = build_strategies_from_json(pm)

    exec_mgr = ExecutionManager.from_json(
        price_manager=pm,
        position_manager=pmgr,
        json_path=EXEC_SETTINGS_PATH,
        starting_cash=pmgr.get_cash(),
    )

    order_mgr = OrderManager(
        initial_capital=pmgr.get_cash(),
        max_orders_per_minute=60,
        max_position_size=10_000,
    )

    bt = Backtester(
        config_path=CONFIG_PATH,
        price_manager=pm,
        position_manager=pmgr,
        strategies_by_symbol=strategies_by_symbol,
        execution_manager=exec_mgr,
        order_manager=order_mgr,
    )

    bt.run()

    eq_df = bt.get_equity_curve_dataframe()
    trade_df = bt.get_trade_dataframe()

    if not eq_df.empty:
        # use bar index instead of timestamp on x-axis
        eq_reset = eq_df.reset_index(drop=True)

        plt.plot(eq_reset.index, eq_reset["equity"])
        plt.title("Equity curve")
        plt.xlabel("Bar index")  # or "Step"
        plt.ylabel("Equity")
        plt.tight_layout()
        plt.show()


    print("Trade log head:")
    if not trade_df.empty:
        print(trade_df.head())


if __name__ == "__main__":
    main()
