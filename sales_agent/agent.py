# sales_agent/agent.py

from google.adk.agents import Agent
from . import prompts # Import the prompts module we just created

# Define the main agent for extracting action items.
# Renamed from root_agent for clarity, matching app.py usage.
action_item_agent = Agent(
    # As requested, using the flash model referenced in the Colab tutorial examples.
    # You can change this model later if needed.
    model="gemini-2.0-flash-001",
    name="action_item_extractor", # Keep the internal name if desired
    description=(
        "Analyzes a sales call transcript to extract action items for Adi Tiwari."
    ),
    # The instructions are dynamically loaded from our prompts.py file.
    instruction=prompts.get_action_item_instructions(),
    # This agent does not need external tools.
    tools=[],
)