# sales_agent/agent.py

from google.adk.agents import Agent
from . import prompts # Import the prompts module we just created

# Define the main agent for extracting action items.
# This structure mirrors the agent definitions in the ADK Quickstart
# (weather_time_agent) and the RAG sample (root_agent).
root_agent = Agent(
    # As requested, using the flash model referenced in the Colab tutorial examples.
    # You can change this model later if needed.
    model="gemini-2.0-flash-001",
    name="action_item_extractor",
    description=(
        "Analyzes a sales call transcript to extract action items for Adi Tiwari."
    ),
    # The instructions are dynamically loaded from our prompts.py file.
    # This follows the pattern used in the RAG sample (instruction=return_instructions_root()).
    instruction=prompts.get_action_item_instructions(),

    # For this initial version, the agent only needs to reason over the
    # provided transcript text based on its instructions. It does not
    # need external tools (like weather, search, or database lookup).
    # Therefore, the tools list is empty. If PDF parsing were a tool,
    # it would be listed here.
    tools=[],
)
