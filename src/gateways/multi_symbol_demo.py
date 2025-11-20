from src.gateways.multi_historical_data_gateway import MultiHistoricalDataGateway


def main():
    gateway = MultiHistoricalDataGateway(
        "settings/market_data_config.json"
    )

    for step in range(5):
        ticks = gateway.get_next_tick()
        if ticks is None:
            print("No more data.")
            break

        print(f"Step {step}")
        for ticker, (ts, row) in ticks.items():
            close_price = row.get("Close", None)
            print(f"  {ticker} {ts} Close={close_price}")


if __name__ == "__main__":
    main()