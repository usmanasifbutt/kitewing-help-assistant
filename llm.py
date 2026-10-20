"""llm.py - the one place that creates chat models and explains model errors.

generate.py and evaluate.py both call a model; they get it from here. One setting,
LLM_PROVIDER, switches every model call between local Ollama (the default, free) and
OpenAI (optional, much faster). No other file needs to know which provider is active.
"""
import os
from functools import lru_cache

import config
import problems


class GenerationProblem(problems.Problem):
    """A predictable model problem. The message tells the user what to do next."""


@lru_cache(maxsize=None)
def get_chat_model(model, max_tokens, json_mode=False):
    """Build (once) the chat model for the active provider. json_mode makes it answer with JSON only."""
    if config.LLM_PROVIDER == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise GenerationProblem("langchain-openai is not installed. Run: pip install -r requirements.txt")
        if not os.environ.get("OPENAI_API_KEY"):
            raise GenerationProblem("OPENAI_API_KEY is not set. Add it to your .env file (never commit it), "
                                    "or switch back to the free local model with LLM_PROVIDER=ollama.")
        chat_model = ChatOpenAI(model=model, temperature=0, max_tokens=max_tokens)
        return chat_model.bind(response_format={"type": "json_object"}) if json_mode else chat_model

    from langchain_ollama import ChatOllama
    return ChatOllama(model=model, base_url=config.OLLAMA_URL, temperature=0, num_predict=max_tokens,
                      format="json" if json_mode else None)


def explain(error):
    """Turn a model error into a GenerationProblem with a next step, or None if we do not recognise it."""
    text = f"{type(error).__name__} {error}".lower()
    if config.LLM_PROVIDER == "openai":
        if "api key" in text or "authentication" in text or "401" in text:
            return GenerationProblem("OpenAI rejected the API key. Check OPENAI_API_KEY in your .env file.")
        if "rate limit" in text or "quota" in text or "429" in text:
            return GenerationProblem("OpenAI rate limit or quota reached. Wait a minute, or check your OpenAI billing.")
        if "connect" in text or "timeout" in text:
            return GenerationProblem("Could not reach OpenAI. Check your internet connection and try again.")
        if "model" in text and ("not found" in text or "does not exist" in text):
            return GenerationProblem(f"OpenAI does not know the model {config.LLM_MODEL}. Check OPENAI_LLM_MODEL in .env.")
        return None
    if "connect" in text or "refused" in text:
        return GenerationProblem("Ollama is not running. Start the Ollama app (or run: ollama serve) and try again.")
    if "not found" in text:
        models = " and ".join(dict.fromkeys((config.LLM_MODEL, config.JUDGE_MODEL)))
        return GenerationProblem(f"A model is not downloaded in Ollama. Run: ollama pull <name> for each of: {models}")
    return None


def ask(chat_model, messages):
    """Call a chat model; predictable failures become a GenerationProblem with a clear message."""
    try:
        return chat_model.invoke(messages).content
    except Exception as error:
        problem = explain(error)
        if problem:
            raise problem from error
        raise
