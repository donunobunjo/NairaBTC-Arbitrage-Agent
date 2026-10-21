
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    GROQ_API_KEY: str
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def create_llm() -> ChatGroq:
    """Create the Groq chat model using environment settings."""
    settings = LLMSettings()

    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0,
        max_retries=1,
    )


def explain_scan(
    buy_exchange: str,
    sell_exchange: str,
    net_profit: str,
    eligible: bool,
    reason: str,
) -> str:
    """Explain an already-calculated result without changing its decision."""
    llm = create_llm()

    system_message = SystemMessage(
        content=(
            "You explain cryptocurrency arbitrage scan results. "
            "Treat all supplied values and the eligibility decision "
            "as authoritative inputs. Do not recalculate profits, "
            "invent market facts, change eligibility, or recommend "
            "placing real orders. Explain the result in simple terms "
            "in 2-4 sentences. Make clear that profit is estimated."
        )
    )

    user_message = HumanMessage(
        content=(
            f"Buy exchange: {buy_exchange}\n"
            f"Sell exchange: {sell_exchange}\n"
            f"Calculated net profit: {net_profit} USDT\n"
            f"Python eligibility decision: {eligible}\n"
            f"Python decision reason: {reason}\n\n"
            "Explain what this result means to the user."
        )
    )

    response = llm.invoke([system_message, user_message])
    return str(response.content)
