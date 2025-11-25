# Backtest Results

## Execution Sensitivity (Sharpe ratio)
| weight_per_strength_unit \ max_symbol_weight | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 |
|---|---|---|---|---|---|
| 0.00 | -5.281893 | -6.165506 | -6.590617 | -2.919366 | -3.587455 |
| 0.01 | -3.926616 | -2.021618 | -2.794935 | -1.565105 | -2.233639 |
| 0.02 | -3.241461 | -2.764073 | -3.108943 | -1.362057 | -5.546182 |
| 0.03 | 0.205846 | -3.052675 | -0.612378 | 0.053498 | 1.863061 |
| 0.04 | -1.946322 | -2.838200 | -2.794466 | -4.152159 | 1.962354 |

## Strategy Weight Sensitivity META MomentumStrategy (Sharpe ratio)
| META_MomentumStrategy_weight | sharpe |
|---|---|
| 0.25 | -4.037744 |
| 0.50 | -5.522808 |
| 1.00 | -3.241461 |
| 1.50 | -2.185359 |
| 2.00 | -1.374275 |

## Strategy Weight Sensitivity META MovingAverageCrossoverStrategy (Sharpe ratio)
| META_MovingAverageCrossoverStrategy_weight | sharpe |
|---|---|
| 0.25 | -7.173407 |
| 0.50 | -3.241461 |
| 1.00 | -0.729123 |
| 1.50 | -3.287755 |
| 2.00 | -4.819413 |

## Strategy Weight Sensitivity META RsiReversionStrategy (Sharpe ratio)
| META_RsiReversionStrategy_weight | sharpe |
|---|---|
| 0.25 | -3.552436 |
| 0.50 | -3.413940 |
| 1.00 | -3.241461 |
| 1.50 | -3.711652 |
| 2.00 | -4.510487 |

## META MomentumStrategy Period vs Threshold Sensitivity (Sharpe ratio)
| momentum_period \ momentum_threshold | 0.01 | 0.02 | 0.03 | 0.05 |
|---|---|---|---|---|
| 10 | -4.813786 | -1.008863 | -2.876325 | -2.731088 |
| 20 | -6.687004 | -3.241461 | -3.013272 | -2.202977 |
| 40 | -6.069400 | -1.177476 | -2.825443 | -1.937143 |
| 60 | -3.376133 | -1.254288 | -3.440014 | -5.162914 |

## META MovingAverageCrossoverStrategy Fast vs Slow (Sharpe ratio)
| mac_fast \ mac_slow | 30 | 50 | 100 |
|---|---|---|---|
| 5  | 4.443655 | -2.537026 | -2.673351 |
| 10 | -0.175473 | -3.241461 | -4.377304 |
| 20 | -2.170515 | -0.843421 | -5.324820 |

## META RsiReversionStrategy Overbought vs Oversold (Sharpe ratio)
| rsi_overbought \ rsi_oversold | 20 | 30 | 40 |
|---|---|---|---|
| 60 | -2.519956 | -2.646417 | 2.522607 |
| 70 | -5.940324 | -3.241461 | 0.168839 |
| 80 | -4.962023 | -4.275955 | -1.929818 |
