ASSET_UNIVERSE = [
    {"ticker": "NIFTYBEES.NS", "name": "Nippon India ETF Nifty BeES", "asset_class": "Indian Large-Cap Equity"},
    {"ticker": "JUNIORBEES.NS", "name": "Nippon India ETF Junior BeES", "asset_class": "Indian Mid-Cap Equity"},
    {"ticker": "BANKBEES.NS", "name": "Nippon India ETF Bank BeES", "asset_class": "Indian Financials"},
    {"ticker": "ITBEES.NS", "name": "Nippon India ETF IT BeES", "asset_class": "Indian IT Sector"},
    {"ticker": "MON100.NS", "name": "Motilal Oswal Nasdaq 100 ETF", "asset_class": "International Equity (US Tech)"},
    {"ticker": "GILT5YBEES.NS", "name": "Nippon India ETF Nifty 5yr Benchmark G-Sec", "asset_class": "Indian Government Bonds"},
    {"ticker": "LIQUIDBEES.NS", "name": "Nippon India ETF Liquid BeES", "asset_class": "Cash / Money Market"},
    {"ticker": "GOLDBEES.NS", "name": "Nippon India ETF Gold BeES", "asset_class": "Gold"},
    {"ticker": "SILVERBEES.NS", "name": "Nippon India ETF Silver BeES", "asset_class": "Silver"},
]

TICKERS = [asset["ticker"] for asset in ASSET_UNIVERSE]

ASSET_BY_TICKER = {asset["ticker"]: asset for asset in ASSET_UNIVERSE}
