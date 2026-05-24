import os
from datetime import date

import streamlit as st


AGENTS = {
    "Orchestrator": {
        "description": "Loads OHLCV once and fans out to indicators + patterns + TA in parallel, then synthesises a structured markdown report via GPT-4o.",
        "factory": "techa.agents.orchestrator:create_orchestrator",
        "multi_symbol": False,
    },
    "Indicator": {
        "description": "Trend, momentum and volatility snapshot from raw OHLCV.",
        "factory": "techa.agents.indicators:create_indicator_agent",
        "multi_symbol": False,
    },
    "TA": {
        "description": "Moving-average crossover + range breakout analysis vs benchmark.",
        "factory": "techa.agents.ta:create_manager",
        "multi_symbol": False,
    },
    "Pattern": {
        "description": "Scans one or more tickers for 61 TA-Lib candlestick patterns.",
        "factory": "techa.agents.patterns:create_pattern_agent",
        "multi_symbol": True,
    },
}


def get_openai_key() -> str | None:
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return os.environ.get("OPENAI_API_KEY")


def import_factory(dotted: str):
    module_path, attr = dotted.split(":")
    module = __import__(module_path, fromlist=[attr])
    return getattr(module, attr)


def build_graph(agent_name: str, params: dict):
    factory = import_factory(AGENTS[agent_name]["factory"])
    if agent_name == "Orchestrator":
        return factory(
            symbol=params["symbol"],
            data_source=params["data_source"],
            analysis_date=params["analysis_date"],
            lookback_days=params["lookback_days"],
            benchmark=params["benchmark"],
            relative=params["relative"],
        )
    if agent_name == "Indicator":
        return factory(params["symbol"], data_source=params["data_source"])
    if agent_name == "TA":
        return factory(params["symbol"], analysis_date=params["analysis_date"])
    if agent_name == "Pattern":
        return factory(params["symbols"], signal_filter=params["signal_filter"])
    raise ValueError(f"Unknown agent: {agent_name}")


def extract_output(result: dict) -> str:
    for key in ("final_output", "report", "output", "summary"):
        if key in result and isinstance(result[key], str):
            return result[key]
    return f"```json\n{result}\n```"


st.set_page_config(page_title="techa · Trading Agents", page_icon="📈", layout="wide")
st.title("📈 techa — Trading Agents")
st.caption(
    "Streamlit front-end for [laceto/techa](https://github.com/laceto/techa): "
    "TA-Lib-backed indicators, candlestick patterns, MA trends and a LangGraph orchestrator."
)

api_key = get_openai_key()
if not api_key:
    st.warning("Set your OpenAI API key to run the agents:")
    st.code("export OPENAI_API_KEY=sk-...")
    st.markdown("Or `.streamlit/secrets.toml`:")
    st.code('OPENAI_API_KEY = "sk-..."')
    st.stop()
os.environ["OPENAI_API_KEY"] = api_key

with st.sidebar:
    st.header("Agent")
    agent_name = st.selectbox("Select agent", list(AGENTS.keys()))
    st.caption(AGENTS[agent_name]["description"])

    st.header("Inputs")
    if AGENTS[agent_name]["multi_symbol"]:
        symbols_raw = st.text_input("Tickers (comma-separated)", value="A2A.MI, ENI.MI")
        symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]
    else:
        symbol = st.text_input("Ticker", value="PST.MI")

    data_source = st.selectbox("Data source", ["live", "parquet"], index=0)
    benchmark = st.text_input("Benchmark", value="FTSEMIB.MI")
    lookback_days = st.number_input("Lookback (days)", min_value=60, max_value=2000, value=365, step=30)
    use_date_ceiling = st.checkbox("Pin analysis date", value=False)
    analysis_date = st.date_input("Analysis date", value=date.today()) if use_date_ceiling else None
    relative = st.checkbox("Relative pricing (stock / benchmark)", value=False)
    signal_filter = st.selectbox("Pattern signal filter", ["all", "bull", "bear"], index=0)

    run = st.button("▶ Run agent", type="primary", use_container_width=True)

if not run:
    st.info("Configure inputs in the sidebar and press **Run agent**.")
    st.stop()

params = {
    "symbol": symbol if not AGENTS[agent_name]["multi_symbol"] else None,
    "symbols": symbols if AGENTS[agent_name]["multi_symbol"] else None,
    "data_source": data_source,
    "analysis_date": analysis_date.isoformat() if analysis_date else None,
    "lookback_days": int(lookback_days),
    "benchmark": benchmark,
    "relative": relative,
    "signal_filter": signal_filter,
}

label = ", ".join(params["symbols"]) if AGENTS[agent_name]["multi_symbol"] else params["symbol"]
with st.spinner(f"Running {agent_name} agent on {label}…"):
    try:
        graph = build_graph(agent_name, params)
        result = graph.invoke(graph._initial_state)
    except ImportError as e:
        st.error(
            "Failed to import `techa`. Install it first:\n\n"
            "```\npip install git+https://github.com/laceto/techa.git\n```\n\n"
            "Note: TA-Lib's C library must already be installed on the host. "
            f"Original error: {e}"
        )
        st.stop()
    except Exception as e:
        st.error(f"Agent failed: {type(e).__name__}: {e}")
        st.stop()

st.success(f"{agent_name} agent finished.")
st.markdown(extract_output(result))

with st.expander("Raw result"):
    st.json({k: v for k, v in result.items() if k != "final_output"})

st.caption(
    "⚠️ This is an automated technical analysis tool, not investment advice. "
    "Always validate signals against your own research before trading."
)
