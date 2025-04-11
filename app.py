# app.py

import streamlit as st
import os
import io
import PyPDF2
import asyncio
import logging # Import logging module
from dotenv import load_dotenv

# --- Set page config FIRST ---
st.set_page_config(layout="wide")

# --- Configure Logging ---
# Set basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Streamlit app started.")

# Import ADK components
try:
    from google.adk.agents import Agent
    from google.adk.sessions import InMemorySessionService
    from google.adk.runners import Runner
    from google.genai import types as genai_types # Renamed
    adk_imported = True
    logging.info("ADK components imported successfully.")
except ImportError as e:
    logging.error(f"Failed to import ADK components: {e}")
    st.error(f"Failed to import core ADK components: {e}. Please ensure google-adk is installed.")
    adk_imported = False


# --- Configuration and Setup ---

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), 'sales_agent', '.env')
load_dotenv(dotenv_path=dotenv_path)
logging.info("Attempted to load .env file.")

# Check API key status
api_key_placeholder = "PASTE_YOUR_ACTUAL_GOOGLE_API_KEY_HERE"
loaded_key = os.getenv("GOOGLE_API_KEY")
api_key_properly_set = bool(loaded_key and loaded_key != api_key_placeholder)
if api_key_properly_set:
    logging.info("Google API Key found in environment.")
else:
    logging.warning("Google API Key not found or is placeholder in .env.")

# --- Initialize Streamlit Session State ---
if 'transcript_text' not in st.session_state: st.session_state.transcript_text = None
if 'action_items' not in st.session_state: st.session_state.action_items = None
if 'follow_up_email' not in st.session_state: st.session_state.follow_up_email = None # New state for email
if 'processing_action_items' not in st.session_state: st.session_state.processing_action_items = False
if 'processing_email' not in st.session_state: st.session_state.processing_email = False # New state for email processing

# --- Load Agents (only if ADK was imported) ---
action_agent_loaded = False
email_agent_loaded = False
action_item_agent = None # Renamed from root_agent for clarity
email_agent = None       # New email agent variable
if adk_imported:
    try:
        # Import both agents from the sales_agent package
        from sales_agent import action_item_agent as imported_action_agent # Use alias if needed
        from sales_agent import email_follow_up_agent as imported_email_agent
        action_item_agent = imported_action_agent
        email_agent = imported_email_agent
        action_agent_loaded = True
        email_agent_loaded = True
        logging.info("Action Item and Email agents loaded successfully.")
    except ImportError as e:
        st.error(f"Error importing agents: {e}. Check sales_agent files.")
        logging.error(f"Error importing agents: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred while loading agents: {e}")
        logging.error(f"An unexpected error occurred while loading agents: {e}")

# --- Initialize ADK Runners (only if agents loaded and API key set) ---
session_service = None
action_item_runner = None # Renamed for clarity
email_runner = None       # New runner for email
# Define constants for runner context (can be shared or distinct)
APP_NAME = "sales_transcript_analyzer"
USER_ID = "local_user"
SESSION_ID = "transcript_session" # Using same session for simplicity, could be different

if action_agent_loaded and email_agent_loaded and api_key_properly_set:
    try:
        session_service = InMemorySessionService()
        logging.info("ADK InMemorySessionService initialized.")
        # Explicitly create the session
        try:
            session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
            logging.info(f"ADK Session '{SESSION_ID}' created for user '{USER_ID}'.")
        except Exception as create_session_e:
             logging.warning(f"Could not create session '{SESSION_ID}' (might already exist): {create_session_e}")
             if not session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID):
                  logging.error(f"Failed to ensure session '{SESSION_ID}' exists.")
                  raise Exception(f"Failed to ensure session '{SESSION_ID}' exists.") from create_session_e

        # Create the runner for the Action Item agent
        action_item_runner = Runner(
            agent=action_item_agent,
            app_name=APP_NAME,
            session_service=session_service
        )
        logging.info("Action Item Runner initialized.")

        # Create the runner for the Email agent
        email_runner = Runner(
            agent=email_agent,
            app_name=APP_NAME, # Can reuse app name
            session_service=session_service # Can reuse session service
        )
        logging.info("Email Runner initialized.")

    except Exception as adk_setup_e:
         st.error(f"Failed to initialize ADK Runner/Session: {adk_setup_e}")
         logging.error(f"Failed to initialize ADK Runner/Session: {adk_setup_e}")
         action_item_runner = None # Ensure runners are None on failure
         email_runner = None
else:
    action_item_runner = None
    email_runner = None
    if not (action_agent_loaded and email_agent_loaded) and api_key_properly_set:
        st.error("One or more agent definitions could not be loaded. Cannot initialize ADK Runners.")
        logging.error("Agent definition(s) could not be loaded.")


# --- Helper Functions ---
def extract_text_from_pdf(uploaded_file):
    logging.info(f"Attempting to extract text from PDF: {uploaded_file.name}")
    try:
        pdf_bytes = io.BytesIO(uploaded_file.getvalue())
        reader = PyPDF2.PdfReader(pdf_bytes)
        text = ""
        if reader.is_encrypted:
             st.error("Cannot process encrypted PDF files.")
             logging.error("PDF is encrypted.")
             return None
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as page_err:
                 logging.warning(f"Could not extract text from page {i+1}: {page_err}")
                 st.warning(f"Could not extract text from page {i+1}.")

        if not text:
             st.warning("No text could be extracted from the PDF. Please ensure it's text-based.")
             logging.warning("No text extracted from PDF.")
             return None
        logging.info("PDF text extraction successful.")
        return text
    except PyPDF2.errors.PdfReadError as pdf_err:
        st.error(f"Error reading PDF: {pdf_err}. Please ensure it's a valid, text-based PDF.")
        logging.error(f"PyPDF2 read error: {pdf_err}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during PDF parsing: {e}")
        logging.exception("Unexpected PDF parsing error.") # Log full traceback
        return None

async def run_adk_agent_async(transcript_text, runner_instance, task_description):
    """Generic function to run an ADK agent via its runner."""
    global USER_ID, SESSION_ID # Use global IDs
    if not runner_instance:
        st.error(f"ADK Runner for {task_description} not initialized. Cannot process request.")
        logging.error(f"Runner for {task_description} not initialized.")
        return None
    logging.info(f"Running {task_description} agent...")
    try:
        content = genai_types.Content(role='user', parts=[genai_types.Part(text=transcript_text)])
        final_response_text = f"{task_description} agent did not produce a final response."
        async for event in runner_instance.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
                    logging.info(f"{task_description} agent finished successfully.")
                elif event.actions and event.actions.escalate:
                    error_msg = event.error_message or 'No specific message.'
                    final_response_text = f"Agent Error during {task_description}: {error_msg}"
                    st.error(final_response_text)
                    logging.error(f"Agent Error during {task_description}: {error_msg}")
                break
        return final_response_text
    except Exception as e:
        st.error(f"An error occurred while running the {task_description} agent: {e}")
        logging.exception(f"Error during {task_description} agent execution") # Log traceback
        return None

# --- Streamlit UI ---

st.title("Sales Call Transcript Analyzer")

# Display warning if API key is not properly set in .env
if not api_key_properly_set:
    st.warning(f"⚠️ Google API Key not found or is still the placeholder in `sales_agent/.env`. Please add your valid key.")

# Determine if base requirements (key, agents, runners) are met
base_setup_ok = api_key_properly_set and action_agent_loaded and email_agent_loaded and action_item_runner and email_runner

# File Uploader
uploaded_file = st.file_uploader(
    "1. Upload Transcript PDF",
    type="pdf",
    help="Upload a text-based PDF transcript of your sales call.",
    disabled=not base_setup_ok, # Disable if base setup failed
    # Clear state on new upload
    on_change=lambda: st.session_state.update(transcript_text=None, action_items=None, follow_up_email=None, processing_action_items=False, processing_email=False)
)

# --- PDF Processing ---
if uploaded_file is not None and st.session_state.transcript_text is None:
    if base_setup_ok: # Only process if setup is okay
        logging.info(f"Processing uploaded file: {uploaded_file.name}")
        with st.spinner("Extracting text from PDF..."):
            extracted_text = extract_text_from_pdf(uploaded_file)
            if extracted_text:
                st.session_state.transcript_text = extracted_text
                st.success("PDF text extracted successfully. Ready to analyze.")
            else:
                st.session_state.transcript_text = None

# --- Analysis Buttons and Results ---
if st.session_state.transcript_text:
    st.markdown("---") # Separator
    st.subheader("2. Choose Analysis:")

    col1, col2 = st.columns(2) # Create two columns for buttons

    with col1:
        analyze_action_items_button = st.button(
            "Get Adi's Action Items",
            key="analyze_action_items_btn",
            disabled=st.session_state.processing_action_items or st.session_state.processing_email, # Disable if any processing
            use_container_width=True
        )
        if analyze_action_items_button:
            st.session_state.processing_action_items = True
            st.session_state.action_items = None # Clear previous results
            st.rerun() # Rerun to show spinner immediately

    with col2:
        generate_email_button = st.button(
            "Generate Follow-up Email",
            key="generate_email_btn",
            disabled=st.session_state.processing_action_items or st.session_state.processing_email, # Disable if any processing
            use_container_width=True
        )
        if generate_email_button:
            st.session_state.processing_email = True
            st.session_state.follow_up_email = None # Clear previous results
            st.rerun() # Rerun to show spinner immediately

    # --- Display Action Items ---
    if st.session_state.processing_action_items:
        with st.spinner("Extracting action items..."):
             action_items_result = asyncio.run(run_adk_agent_async(st.session_state.transcript_text, action_item_runner, "Action Item"))
             st.session_state.action_items = action_items_result
             st.session_state.processing_action_items = False
             st.rerun() # Rerun to display results

    if st.session_state.action_items:
        st.markdown("---")
        st.subheader("Action Items for Adi Tiwari:")
        if "Agent Error:" not in st.session_state.action_items:
            st.markdown(st.session_state.action_items)
        else:
            st.info("Could not extract action items due to an agent processing error (see error message above).")

    # --- Display Email ---
    if st.session_state.processing_email:
        with st.spinner("Generating follow-up email..."):
            email_result = asyncio.run(run_adk_agent_async(st.session_state.transcript_text, email_runner, "Email Generation"))
            st.session_state.follow_up_email = email_result
            st.session_state.processing_email = False
            st.rerun() # Rerun to display results

    if st.session_state.follow_up_email:
        st.markdown("---")
        st.subheader("Generated Follow-up Email Body:")
        if "Agent Error:" not in st.session_state.follow_up_email:
            st.text_area("Email Body", st.session_state.follow_up_email, height=300)
        else:
            st.info("Could not generate email due to an agent processing error (see error message above).")


# Add a footer or instruction if the uploader is disabled
if not base_setup_ok:
    st.info("File uploader is disabled. Please ensure a valid Google API Key is set in `sales_agent/.env` and the agent components loaded correctly.")
    logging.warning("Uploader disabled due to failed setup.")