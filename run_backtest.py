import json

import matplotlib.pyplot as plt

from src.backtester import Backtester, WeightedStrategy
from src.price_manager import PriceManager
from src.execution_manager import ExecutionManager
from src.order_manager import OrderManager
from src.position_manager import PositionManager
from src.logger_gateway import OrderLogger, SignalLogger
from src import strategies as strat_mod


CONFIG_PATH = "src/settings/market_data_config.json"
STRATEGY_CONFIG_PATH = "src/settings/strategy_config.json"
EXEC_SETTINGS_PATH = "src/settings/execution_settings.json"
INITIAL_PORTFOLIO_PATH = "src/settings/initial_positions.json"


def build_strategies_from_json(pm: PriceManager, strat_cfg: dict) -> dict:
    strategies_by_symbol: dict = {}

    for symbol, strat_list in strat_cfg.items():
        strategies_by_symbol[symbol] = []

        for entry in strat_list:
            class_name = entry["class"]
            weight = entry.get("weight", 1.0)
            params = entry.get("params", {})

            cls = getattr(strat_mod, class_name, None)
            if cls is None:
                raise ValueError(
                    f"Strategy class '{class_name}' not found in src.strategies"
                )

            strat_instance = cls(price_manager=pm, symbol=symbol, **params)

            strategies_by_symbol[symbol].append(
                WeightedStrategy(strategy=strat_instance, weight=weight)
            )

    return strategies_by_symbol


def main():
    # load all configs
    with open(CONFIG_PATH, "r") as f:
        market_cfg = json.load(f)

    with open(STRATEGY_CONFIG_PATH, "r") as f:
        strat_cfg = json.load(f)

    with open(EXEC_SETTINGS_PATH, "r") as f:
        exec_cfg = json.load(f)

    with open(INITIAL_PORTFOLIO_PATH, "r") as f:
        init_portfolio_cfg = json.load(f)

    order_mgr_params = {
        "max_orders_per_minute": 60,
        "max_position_size": 10_000,
    }

    # portfolio and price manager
    pmgr = PositionManager.from_json(INITIAL_PORTFOLIO_PATH)
    pm = PriceManager(max_history=200)

    # strategies per symbol
    strategies_by_symbol = build_strategies_from_json(pm, strat_cfg)

    # loggers
    order_logger = OrderLogger()
    signal_logger = SignalLogger()

    # execution and risk
    exec_mgr = ExecutionManager(
        price_manager=pm,
        position_manager=pmgr,
        starting_cash=pmgr.get_cash(),
        settings_dict=exec_cfg,
    )

    order_mgr = OrderManager(
        initial_capital=pmgr.get_cash(),
        max_orders_per_minute=order_mgr_params["max_orders_per_minute"],
        max_position_size=order_mgr_params["max_position_size"],
        order_logger=order_logger,
    )

    # backtester
    bt = Backtester(
        config_path=CONFIG_PATH,
        price_manager=pm,
        position_manager=pmgr,
        strategies_by_symbol=strategies_by_symbol,
        execution_manager=exec_mgr,
        order_manager=order_mgr,
        order_logger=order_logger,
        signal_logger=signal_logger,
        market_cfg=market_cfg,
        strat_cfg=strat_cfg,
        exec_cfg=exec_cfg,
        init_portfolio_cfg=init_portfolio_cfg,
        order_mgr_params=order_mgr_params,
    )

    bt.run()

    # equity by step index
    eq_df = bt.get_equity_curve_dataframe()
    trade_df = bt.get_trade_dataframe()

    if not eq_df.empty:
        eq_reset = eq_df.reset_index(drop=True)

        plt.plot(eq_reset.index, eq_reset["equity"])
        plt.title("Equity curve")
        plt.xlabel("Bar index")
        plt.ylabel("Equity")
        plt.tight_layout()
        plt.show()

    print("Trade log head:")
    if not trade_df.empty:
        print(trade_df.head())


if __name__ == "__main__":
    main()
