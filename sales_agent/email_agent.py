# sales_agent/email_agent.py

from google.adk.agents import Agent
from . import email_prompts # Import the new prompts module

# Define the agent specifically for generating follow-up emails.
# It uses the same model configuration but has its own focused instructions.
email_follow_up_agent = Agent(
    model="gemini-2.0-flash-001", # Consistent model choice
    name="email_follow_up_generator",
    description=(
        "Generates a sales follow-up email based on a call transcript."
    ),
    instruction=email_prompts.get_email_follow_up_instructions(),
    # This agent also doesn't need external tools for its core task.
    tools=[],
)