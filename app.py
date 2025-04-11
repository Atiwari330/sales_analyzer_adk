# app.py

import streamlit as st
import os
import io
import PyPDF2 # To read PDF files
import asyncio # To run ADK's async functions
from dotenv import load_dotenv

# Import ADK components
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types as genai_types # Renamed to avoid conflict with built-in types

# --- Configuration and Setup ---

# Load environment variables from the .env file in the sales_agent directory
# This follows the pattern from ADK docs for managing API keys
dotenv_path = os.path.join(os.path.dirname(__file__), 'sales_agent', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Check if API key is loaded (basic check)
api_key_loaded = bool(os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_API_KEY") != "PASTE_YOUR_ACTUAL_GOOGLE_API_KEY_HERE")

# Import the agent definition AFTER loading .env, as agent init might depend on it
try:
    from sales_agent.agent import root_agent
    agent_loaded = True
except ImportError as e:
    st.error(f"Error importing agent: {e}. Make sure sales_agent/agent.py exists and is correct.")
    agent_loaded = False
except Exception as e: # Catch other potential errors during agent loading/init
    st.error(f"An unexpected error occurred while loading the agent: {e}")
    agent_loaded = False

# Initialize ADK Session Service and Runner only if agent loaded successfully
session_service = None
runner = None
if agent_loaded:
    # Use InMemorySessionService for simplicity in this local prototype
    # As shown in Step 1 and subsequent steps of the ADK Colab tutorial
    session_service = InMemorySessionService()

    # Define constants for the runner context (can be static for this simple app)
    APP_NAME = "sales_transcript_analyzer"
    USER_ID = "local_user"
    SESSION_ID = "transcript_session" # A single session for this use case

    # Create the runner instance, linking the agent and session service
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

# --- Helper Functions ---

def extract_text_from_pdf(uploaded_file):
    """Extracts text content from an uploaded PDF file."""
    try:
        # Use BytesIO to handle the uploaded file in memory
        pdf_bytes = io.BytesIO(uploaded_file.getvalue())
        reader = PyPDF2.PdfReader(pdf_bytes)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text: # Ensure text was extracted
                text += page_text + "\n" # Add newline between pages
        return text
    except PyPDF2.errors.PdfReadError:
        st.error("Error reading PDF. Please ensure it's a valid, text-based PDF.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during PDF parsing: {e}")
        return None

async def get_action_items_async(transcript_text):
    """Runs the ADK agent asynchronously to get action items."""
    if not runner:
        st.error("ADK Runner not initialized. Cannot process request.")
        return None

    try:
        # Create the initial message content for the agent
        # Using genai_types as imported
        content = genai_types.Content(role='user', parts=[genai_types.Part(text=transcript_text)])

        # Ensure a session exists (create if not - although runner usually handles this)
        session = session_service.get_session(APP_NAME, USER_ID, SESSION_ID)
        if not session:
           session = session_service.create_session(APP_NAME, USER_ID, SESSION_ID)

        final_response_text = "Agent did not produce a final response." # Default

        # Iterate through events yielded by the runner's async execution
        # This pattern is shown in the ADK Colab tutorial (Step 1, call_agent_async)
        async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
            # Uncomment to debug and see all events
            # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")
            if event.is_final_response():
                if event.content and event.content.parts:
                    # Assuming text response in the first part
                    final_response_text = event.content.parts[0].text
                elif event.actions and event.actions.escalate: # Handle potential errors/escalations
                    final_response_text = f"Agent Error: {event.error_message or 'No specific message.'}"
                break # Stop processing once final response is found

        return final_response_text

    except Exception as e:
        st.error(f"An error occurred while running the agent: {e}")
        # Potentially log the full error for debugging
        print(f"Agent execution error: {e}") # Log to console
        return None


# --- Streamlit UI ---

st.set_page_config(layout="wide")
st.title("Sales Call Transcript Action Item Extractor")

# Display warning if API key is not loaded
if not api_key_loaded:
    st.warning("⚠️ Google API Key not found. Please ensure it is set in `sales_agent/.env`.")

uploaded_file = st.file_uploader(
    "Upload Transcript PDF",
    type="pdf",
    help="Upload a text-based PDF transcript of your sales call.",
    disabled=not api_key_loaded or not agent_loaded or not runner # Disable if setup failed
)

if uploaded_file is not None:
    st.info(f"Processing `{uploaded_file.name}`...")
    with st.spinner("Extracting text from PDF..."):
        transcript_text = extract_text_from_pdf(uploaded_file)

    if transcript_text:
        # st.text_area("Extracted Text (Debug)", transcript_text, height=200) # Optional: Display extracted text for debugging
        st.success("PDF text extracted successfully.")
        with st.spinner("Analyzing transcript and extracting action items for Adi Tiwari..."):
            # Run the async function using asyncio.run()
            # This is a common way to run an async task from sync Streamlit code
            action_items_md = asyncio.run(get_action_items_async(transcript_text))

        if action_items_md:
            st.subheader("Action Items for Adi Tiwari:")
            st.markdown(action_items_md) # Display using markdown as requested
        else:
            # Error messages are handled within get_action_items_async
            st.info("Could not extract action items.")
