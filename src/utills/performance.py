import pandas as pd
import numpy as np

class PerformanceCalculator:
    """
    Calculates all key performance metrics for a backtest.
    This is for Part 3, Step 1.
    
    It takes the complete history of portfolio values and
    calculates P&L, Sharpe Ratio, and Max Drawdown.
    """

    def __init__(self, portfolio_history: pd.Series, risk_free_rate_annual: float = 0.03):
        """
        Initializes the calculator.
        
        Args:
            portfolio_history (pd.Series): A pandas Series with a
                DatetimeIndex and the portfolio's total value
                at each time step.
            risk_free_rate_annual (float): The annualized risk-free
                rate for the Sharpe Ratio (e.g., 0.03 for 3%).
        """
        if portfolio_history.empty:
            raise ValueError("Portfolio history is empty. Cannot calculate metrics.")
            
        self.portfolio_values = portfolio_history
        self.initial_capital = self.portfolio_values.iloc[0]
        self.final_capital = self.portfolio_values.iloc[-1]
        
        # --- Prepare Returns Data ---
        # 1. Resample to daily to get one value per day
        #    We use .last() to get the closing value for that day
        daily_values = self.portfolio_values.resample('D').last().dropna()
        
        # 2. Calculate daily percentage returns
        self.daily_returns = daily_values.pct_change().dropna()
        
        # 3. Calculate daily risk-free rate (assuming 252 trading days)
        self.daily_risk_free = (1 + risk_free_rate_annual)**(1/252) - 1

        print(f"PerformanceCalculator: Initialized with {len(self.portfolio_values)} data points.")

    def get_pnl(self):
        """Calculates total Profit and Loss (P&L)."""
        
        total_pnl_dollars = self.final_capital - self.initial_capital
        total_pnl_percent = (total_pnl_dollars / self.initial_capital) * 100
        
        return {
            "Total P&L ($)": total_pnl_dollars,
            "Total P&L (%)": total_pnl_percent
        }

    def get_sharpe_ratio(self):
        """
        Calculates the annualized Sharpe Ratio.
        [Image of the Sharpe Ratio formula]
        """
        
        # 1. Calculate "excess returns" (returns above the risk-free rate)
        excess_returns = self.daily_returns - self.daily_risk_free
        
        # 2. Calculate mean and standard deviation of excess returns
        mean_excess_return = excess_returns.mean()
        std_dev = excess_returns.std()
        
        # 3. Handle the case where there is no volatility (std_dev = 0)
        if std_dev == 0 or np.isnan(std_dev):
            return 0.0
            
        # 4. Calculate daily Sharpe Ratio
        daily_sharpe = mean_excess_return / std_dev
        
        # 5. Annualize the Sharpe Ratio (sqrt of 252 days)
        annual_sharpe = daily_sharpe * np.sqrt(252)
        
        return annual_sharpe

    def get_max_drawdown(self):
        """
        Calculates the Maximum Drawdown (MDD).
        
        This is the largest drop from a "peak" to a "trough"
        in the portfolio's value.
        """
        
        # 1. Get the "running maximum" (or "high water mark")
        running_max = self.portfolio_values.cummax()
        
        # 2. Calculate the drawdown (how far value is from its peak)
        #    This will be a Series of 0s and negative numbers
        drawdown = (self.portfolio_values - running_max) / running_max
        
        # 3. The max drawdown is the *minimum* (most negative) value
        max_drawdown = drawdown.min()
        
        # Return as a percentage
        return max_drawdown * 100

    def get_all_metrics(self):
        """
        Runs all calculations and returns a single
        dictionary with all key metrics.
        """
        pnl_metrics = self.get_pnl()
        
        metrics = {
            "Start Capital": self.initial_capital,
            "End Capital": self.final_capital,
            "Total P&L ($)": pnl_metrics["Total P&L ($)"],
            "Total P&L (%)": pnl_metrics["Total P&L (%)"],
            "Annualized Sharpe Ratio": self.get_sharpe_ratio(),
            "Max Drawdown (%)": self.get_max_drawdown()
        }
        
        # Round everything for clean printing
        for key, value in metrics.items():
            metrics[key] = round(value, 4)
            
        return metrics