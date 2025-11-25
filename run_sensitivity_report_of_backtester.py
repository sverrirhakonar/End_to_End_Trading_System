# run_sensitivity_report_backtester.py

import json
import copy
import argparse
import os as _os
from typing import Dict, List, Any, Tuple, Optional

import pandas as pd
import multiprocessing as mp

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


# ---------------------------------------------------------------------------
# Strategy construction from JSON
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Load base configs from disk
# ---------------------------------------------------------------------------

def load_base_configs() -> Tuple[dict, dict, dict, dict]:
    with open(CONFIG_PATH, "r") as f:
        market_cfg = json.load(f)

    with open(STRATEGY_CONFIG_PATH, "r") as f:
        strat_cfg = json.load(f)

    with open(EXEC_SETTINGS_PATH, "r") as f:
        exec_cfg = json.load(f)

    with open(INITIAL_PORTFOLIO_PATH, "r") as f:
        init_portfolio_cfg = json.load(f)

    return market_cfg, strat_cfg, exec_cfg, init_portfolio_cfg


# ---------------------------------------------------------------------------
# Annualized Sharpe, same logic as Backtester._final_report
# ---------------------------------------------------------------------------

def compute_annualized_sharpe(eq_df: pd.DataFrame) -> Optional[float]:
    if eq_df.empty:
        return None

    series = eq_df["equity"]
    rets = series.pct_change().dropna()

    if rets.empty:
        return None

    per_period_vol = rets.std()
    per_period_ret = rets.mean()

    if per_period_vol == 0:
        return None

    diffs = eq_df.index.to_series().diff().dropna()
    if diffs.empty:
        return None

    dt_sec = diffs.dt.total_seconds().median()
    if dt_sec <= 0:
        return None

    seconds_per_year = 365.0 * 24.0 * 60.0 * 60.0
    periods_per_year = seconds_per_year / dt_sec

    if periods_per_year <= 0:
        return None

    ann_sharpe = (per_period_ret / per_period_vol) * (periods_per_year ** 0.5)
    return float(ann_sharpe)


# ---------------------------------------------------------------------------
# Core runner for one backtest
# ---------------------------------------------------------------------------

def run_single_backtest(
    market_cfg: dict,
    strat_cfg: dict,
    exec_cfg: dict,
    init_portfolio_cfg: dict,
    order_mgr_params: Dict[str, Any] | None = None,
    config_path: str = CONFIG_PATH,
    initial_portfolio_path: str = INITIAL_PORTFOLIO_PATH,
) -> Tuple[Optional[float], pd.DataFrame, pd.DataFrame]:
    """
    Returns (annualized_sharpe, equity_curve_df, trade_df).
    """

    if order_mgr_params is None:
        order_mgr_params = {
            "max_orders_per_minute": 60,
            "max_position_size": 10_000,
        }

    pmgr = PositionManager.from_json(initial_portfolio_path)
    pm = PriceManager(max_history=200)

    strategies_by_symbol = build_strategies_from_json(pm, strat_cfg)

    order_logger = OrderLogger()
    signal_logger = SignalLogger()

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

    bt = Backtester(
        config_path=config_path,
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

    eq_df = bt.get_equity_curve_dataframe()
    trade_df = bt.get_trade_dataframe()
    sharpe = compute_annualized_sharpe(eq_df)

    return sharpe, eq_df, trade_df


# ---------------------------------------------------------------------------
# Job runner with cache, used in multiprocessing workers
# ---------------------------------------------------------------------------

def run_backtest_job(job: dict) -> dict:
    """
    Worker function for a single job.

    Expects:
      job = {
        "block": str,
        "kind": "exec" | "weight" | "param2d",
        "coord": dict,
        "market_cfg": dict,
        "strat_cfg": dict,
        "exec_cfg": dict,
        "init_portfolio_cfg": dict,
        "order_mgr_params": dict,
        "cache": proxy dict,
    }
    """

    import json as _json
    import copy as _copy

    mc = _copy.deepcopy(job["market_cfg"])
    sc = _copy.deepcopy(job["strat_cfg"])
    ec = _copy.deepcopy(job["exec_cfg"])
    ic = _copy.deepcopy(job["init_portfolio_cfg"])
    order_mgr_params = job["order_mgr_params"]
    kind = job["kind"]
    coord = job["coord"]
    cache = job["cache"]

    if kind == "exec":
        wpsu = coord["weight_per_strength_unit"]
        msw = coord["max_symbol_weight"]
        ec["weight_per_strength_unit"] = wpsu
        ec["max_symbol_weight"] = msw

    elif kind == "weight":
        symbol = coord["symbol"]
        class_name = coord["class_name"]
        new_weight = coord["weight"]
        if symbol in sc:
            for entry in sc[symbol]:
                if entry.get("class") == class_name:
                    entry["weight"] = new_weight

    elif kind == "param2d":
        symbol = coord["symbol"]
        class_name = coord["class_name"]
        param_x = coord["param_x"]
        value_x = coord["value_x"]
        param_y = coord["param_y"]
        value_y = coord["value_y"]

        if symbol in sc:
            for entry in sc[symbol]:
                if entry.get("class") == class_name:
                    params = entry.get("params", {})
                    params[param_x] = value_x
                    params[param_y] = value_y
                    entry["params"] = params

    key_obj = {
        "market_cfg": mc,
        "strat_cfg": sc,
        "exec_cfg": ec,
        "init_portfolio_cfg": ic,
    }
    key = _json.dumps(key_obj, sort_keys=True)

    if key in cache:
        sharpe = cache[key]
    else:
        sharpe, _, _ = run_single_backtest(
            market_cfg=mc,
            strat_cfg=sc,
            exec_cfg=ec,
            init_portfolio_cfg=ic,
            order_mgr_params=order_mgr_params,
        )
        cache[key] = sharpe

    return {
        "block": job["block"],
        "coord": coord,
        "sharpe": sharpe,
    }


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run backtest sensitivity analysis and print Sharpe tables."
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Symbol to run strategy sensitivities on "
             "(if omitted, the first symbol in strategy_config.json is used).",
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=None,
        help="Number of worker processes for multiprocessing "
             "(default uses mp.Pool default).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main: build jobs, run in parallel with cache, then build tables and export
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    market_cfg, strat_cfg, exec_cfg, init_portfolio_cfg = load_base_configs()

    if args.symbol is not None:
        symbol = args.symbol
    else:
        if not strat_cfg:
            raise ValueError("strategy_config.json is empty, cannot infer symbol.")
        symbol = next(iter(strat_cfg.keys()))

    order_mgr_params = {
        "max_orders_per_minute": 60,
        "max_position_size": 10_000,
    }

    # Example grids, edit as desired

    weight_per_strength_unit_values = [0.0, 0.01, 0.02, 0.03, 0.04]
    max_symbol_weight_values = [0.2, 0.4, 0.6, 0.8, 1.0]

    strategy_weight_values = [0.25, 0.5, 1.0, 1.5, 2.0]

    momentum_period_values = [10, 20, 40, 60]
    momentum_threshold_values = [0.01, 0.02, 0.03, 0.05]

    mac_fast_values = [5, 10, 20]
    mac_slow_values = [30, 50, 100]

    rsi_overbought_values = [60, 70, 80]
    rsi_oversold_values = [20, 30, 40]

    jobs: List[dict] = []

    # Execution sensitivity
    for wpsu in weight_per_strength_unit_values:
        for msw in max_symbol_weight_values:
            jobs.append({
                "block": "execution_sensitivity",
                "kind": "exec",
                "coord": {
                    "weight_per_strength_unit": wpsu,
                    "max_symbol_weight": msw,
                },
                "market_cfg": market_cfg,
                "strat_cfg": strat_cfg,
                "exec_cfg": exec_cfg,
                "init_portfolio_cfg": init_portfolio_cfg,
                "order_mgr_params": order_mgr_params,
            })

    # Strategy weights for three strategies
    for class_name in [
        "MomentumStrategy",
        "MovingAverageCrossoverStrategy",
        "RsiReversionStrategy",
    ]:
        for w in strategy_weight_values:
            jobs.append({
                "block": f"weight_{class_name}",
                "kind": "weight",
                "coord": {
                    "symbol": symbol,
                    "class_name": class_name,
                    "weight": w,
                },
                "market_cfg": market_cfg,
                "strat_cfg": strat_cfg,
                "exec_cfg": exec_cfg,
                "init_portfolio_cfg": init_portfolio_cfg,
                "order_mgr_params": order_mgr_params,
            })

    # Momentum params
    for period in momentum_period_values:
        for threshold in momentum_threshold_values:
            jobs.append({
                "block": "params_MomentumStrategy",
                "kind": "param2d",
                "coord": {
                    "symbol": symbol,
                    "class_name": "MomentumStrategy",
                    "param_x": "period",
                    "value_x": period,
                    "param_y": "threshold",
                    "value_y": threshold,
                },
                "market_cfg": market_cfg,
                "strat_cfg": strat_cfg,
                "exec_cfg": exec_cfg,
                "init_portfolio_cfg": init_portfolio_cfg,
                "order_mgr_params": order_mgr_params,
            })

    # Moving average crossover params
    for fast in mac_fast_values:
        for slow in mac_slow_values:
            jobs.append({
                "block": "params_MovingAverageCrossoverStrategy",
                "kind": "param2d",
                "coord": {
                    "symbol": symbol,
                    "class_name": "MovingAverageCrossoverStrategy",
                    "param_x": "fast",
                    "value_x": fast,
                    "param_y": "slow",
                    "value_y": slow,
                },
                "market_cfg": market_cfg,
                "strat_cfg": strat_cfg,
                "exec_cfg": exec_cfg,
                "init_portfolio_cfg": init_portfolio_cfg,
                "order_mgr_params": order_mgr_params,
            })

    # RSI reversion params
    for ob in rsi_overbought_values:
        for os in rsi_oversold_values:
            jobs.append({
                "block": "params_RsiReversionStrategy",
                "kind": "param2d",
                "coord": {
                    "symbol": symbol,
                    "class_name": "RsiReversionStrategy",
                    "param_x": "overbought",
                    "value_x": ob,
                    "param_y": "oversold",
                    "value_y": os,
                },
                "market_cfg": market_cfg,
                "strat_cfg": strat_cfg,
                "exec_cfg": exec_cfg,
                "init_portfolio_cfg": init_portfolio_cfg,
                "order_mgr_params": order_mgr_params,
            })

    total_runs = len(jobs)
    print(f"Total backtests to run: {total_runs}")

    with mp.Manager() as manager:
        cache = manager.dict()

        for job in jobs:
            job["cache"] = cache

        results_by_block: Dict[str, List[dict]] = {}

        with mp.Pool(processes=args.processes) as pool:
            for idx, res in enumerate(pool.imap_unordered(run_backtest_job, jobs), start=1):
                print(f"Completed {idx} / {total_runs} backtests")
                block = res["block"]
                results_by_block.setdefault(block, []).append(res)

        dfs: Dict[str, pd.DataFrame] = {}

        # Execution sensitivity DataFrame
        exec_results = results_by_block.get("execution_sensitivity", [])
        exec_map: Dict[Tuple[float, float], Optional[float]] = {}
        for r in exec_results:
            c = r["coord"]
            key = (c["weight_per_strength_unit"], c["max_symbol_weight"])
            exec_map[key] = r["sharpe"]

        exec_data = []
        for wpsu in weight_per_strength_unit_values:
            row = []
            for msw in max_symbol_weight_values:
                row.append(exec_map.get((wpsu, msw)))
            exec_data.append(row)

        exec_df = pd.DataFrame(
            exec_data,
            index=weight_per_strength_unit_values,
            columns=max_symbol_weight_values,
        )
        exec_df.index.name = "weight_per_strength_unit"
        exec_df.columns.name = "max_symbol_weight"
        dfs["Execution_Sensitivity"] = exec_df

        # Strategy weight DataFrames
        for class_name in [
            "MomentumStrategy",
            "MovingAverageCrossoverStrategy",
            "RsiReversionStrategy",
        ]:
            block_name = f"weight_{class_name}"
            block_results = results_by_block.get(block_name, [])
            weight_map: Dict[float, Optional[float]] = {}
            for r in block_results:
                w = r["coord"]["weight"]
                weight_map[w] = r["sharpe"]
            data = [weight_map.get(w) for w in strategy_weight_values]
            df = pd.DataFrame({"sharpe": data}, index=strategy_weight_values)
            df.index.name = f"{symbol}_{class_name}_weight"
            dfs[f"Weight_{class_name}"] = df

        # Momentum params DataFrame
        mom_results = results_by_block.get("params_MomentumStrategy", [])
        mom_map: Dict[Tuple[int, float], Optional[float]] = {}
        for r in mom_results:
            c = r["coord"]
            key = (c["value_x"], c["value_y"])
            mom_map[key] = r["sharpe"]
        mom_data = []
        for period in momentum_period_values:
            row = []
            for threshold in momentum_threshold_values:
                row.append(mom_map.get((period, threshold)))
            mom_data.append(row)
        mom_df = pd.DataFrame(
            mom_data,
            index=momentum_period_values,
            columns=momentum_threshold_values,
        )
        mom_df.index.name = "momentum_period"
        mom_df.columns.name = "momentum_threshold"
        dfs["Params_MomentumStrategy"] = mom_df

        # Moving average crossover DataFrame
        mac_results = results_by_block.get("params_MovingAverageCrossoverStrategy", [])
        mac_map: Dict[Tuple[int, int], Optional[float]] = {}
        for r in mac_results:
            c = r["coord"]
            key = (c["value_x"], c["value_y"])
            mac_map[key] = r["sharpe"]
        mac_data = []
        for fast in mac_fast_values:
            row = []
            for slow in mac_slow_values:
                row.append(mac_map.get((fast, slow)))
            mac_data.append(row)
        mac_df = pd.DataFrame(
            mac_data,
            index=mac_fast_values,
            columns=mac_slow_values,
        )
        mac_df.index.name = "mac_fast"
        mac_df.columns.name = "mac_slow"
        dfs["Params_MovingAverageCrossoverStrategy"] = mac_df

        # RSI reversion DataFrame
        rsi_results = results_by_block.get("params_RsiReversionStrategy", [])
        rsi_map: Dict[Tuple[float, float], Optional[float]] = {}
        for r in rsi_results:
            c = r["coord"]
            key = (c["value_x"], c["value_y"])
            rsi_map[key] = r["sharpe"]
        rsi_data = []
        for ob in rsi_overbought_values:
            row = []
            for os in rsi_oversold_values:
                row.append(rsi_map.get((ob, os)))
            rsi_data.append(row)
        rsi_df = pd.DataFrame(
            rsi_data,
            index=rsi_overbought_values,
            columns=rsi_oversold_values,
        )
        rsi_df.index.name = "rsi_overbought"
        rsi_df.columns.name = "rsi_oversold"
        dfs["Params_RsiReversionStrategy"] = rsi_df

    # Print tables

    print("\n==============================")
    print("Execution Sensitivity")
    print("==============================")
    print(dfs["Execution_Sensitivity"])

    print("\n==============================")
    print(f"Strategy Weight Sensitivity {symbol} - MomentumStrategy")
    print("==============================")
    print(dfs["Weight_MomentumStrategy"])

    print("\n==============================")
    print(f"Strategy Weight Sensitivity {symbol} - MovingAverageCrossoverStrategy")
    print("==============================")
    print(dfs["Weight_MovingAverageCrossoverStrategy"])

    print("\n==============================")
    print(f"Strategy Weight Sensitivity {symbol} - RsiReversionStrategy")
    print("==============================")
    print(dfs["Weight_RsiReversionStrategy"])

    print("\n==============================")
    print(f"{symbol} MomentumStrategy period vs threshold Sensitivity")
    print("==============================")
    print(dfs["Params_MomentumStrategy"])

    print("\n==============================")
    print(f"{symbol} MovingAverageCrossoverStrategy fast vs slow Sensitivity")
    print("==============================")
    print(dfs["Params_MovingAverageCrossoverStrategy"])

    print("\n==============================")
    print(f"{symbol} RsiReversionStrategy overbought vs oversold Sensitivity")
    print("==============================")
    print(dfs["Params_RsiReversionStrategy"])


if __name__ == "__main__":
    main()
