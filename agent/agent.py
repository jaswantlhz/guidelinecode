"""CPIC RAG Agent — LangGraph ReAct agent for guideline ingestion pipeline."""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from main_tools import tools
import os
from dotenv import load_dotenv

load_dotenv()
openrouter_key = os.getenv("OPENROUTER_API_KEY")

model = ChatOpenAI(
    model="openai/gpt-oss-20b:free",
    temperature=0.1,
    max_tokens=30000,
    timeout=300,
    api_key=openrouter_key,
    base_url="https://openrouter.ai/api/v1",
)

agent = create_react_agent(model, tools)