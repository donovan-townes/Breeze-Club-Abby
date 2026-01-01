import time
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Import from abby_core (sys.path already configured in launch.py)
from abby_core.llm.client import LLMClient
import abby_core.database.mongodb as mongo_db
from abby_core.llm.persona import get_persona, get_persona_by_name
from abby_core.observability.logging import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


# Load the environment variables from .env file
load_dotenv()
llm_client = LLMClient()

# System Prompts
SYSTEM_HELPER = '''
I'm currently talking to {name}, who like these genres: {genre}. I know that their music influences are: {influences}. More about {name}: {description}
'''

# Note: CODER_HELPER was deprecated - code mode no longer used
# All personality behaviors now loaded from abby_core/personality/ config

NO_PROFILE = "This user has not created a profile yet."


def chat(user, user_id, chat_history=[]):
    profile = mongo_db.get_profile(user_id)
    personality_doc = mongo_db.get_personality()
    PERSONALITY_NUMBER = personality_doc['personality_number'] if personality_doc else 0.6
    active_persona_doc = get_persona()
    active_persona = active_persona_doc.get('active_persona', 'bunny') if active_persona_doc else 'bunny'
    persona_doc = get_persona_by_name(active_persona)
    persona_message = persona_doc.get('persona_message', '') if persona_doc else "I'm Abby, A bunny assistant for the Breeze Club Discord!"

    try:
        messages = []

        if profile is None:
            system_helper_message = NO_PROFILE
        else:
            # Check if creative_profile exists with required fields
            creative_profile = profile.get('creative_profile', {})
            if not all(key in creative_profile for key in ['name', 'description', 'genre', 'influences']):
                # Profile exists but creative_profile is missing required fields
                logger.debug(f"Creative profile incomplete for user {user_id}, using NO_PROFILE fallback")
                system_helper_message = NO_PROFILE
            else:
                system_helper_message = SYSTEM_HELPER.format(
                    name=creative_profile['name'], description=creative_profile['description'], genre=creative_profile['genre'], influences=creative_profile['influences'])

        messages.append({"role": "system", "content": persona_message})
        messages.append({"role": "system", "content": system_helper_message})
        
        # Add chat history (last 4 exchanges)
        for message in chat_history[-4:]:
            messages.append({"role": "user", "content": message["input"]})
            messages.append({"role": "assistant", "content": message["response"]})

        messages.append({"role": "user", "content": user})

        retry_count = 0
        while retry_count < 3:
            try:
                return llm_client.chat(
                    messages,
                    request_type="chat",
                    temperature=PERSONALITY_NUMBER,
                    invoker_subject_id=f"SUBJECT:DISCORD-USER-{user_id}",
                    task_priority="high",  # User-facing: fast response required
                )
            except Exception as e:
                logger.warning(
                    f"An error occurred while processing the chat request: {str(e)}")
                logger.info("Retrying...")
                time.sleep(1)
                retry_count += 1

        return "Oops, something went wrong. Please try again later."

    except Exception as e:
        logging.warning(
            f"An error occurred while processing the chat request: {str(e)}")
        return "Oops, something went wrong. Please try again later."


def summarize(chat_session):
    """Generate a summary from chat history.
    
    Args:
        chat_session: List of dicts with 'input' and 'response' keys, or a string
    """
    retry_count = 0
    
    # Convert chat_session list to formatted string
    if isinstance(chat_session, list):
        formatted_text = "\n\n".join([
            f"User: {item.get('input', '')}\nAbby: {item.get('response', '')}"
            for item in chat_session
            if isinstance(item, dict) and (item.get('input') or item.get('response'))
        ])
        chat_text = formatted_text if formatted_text else str(chat_session)
    else:
        chat_text = str(chat_session)
    
    while retry_count < 3:
        try:
            return llm_client.summarize(chat_text, max_tokens=300)
        except Exception as e:
            logging.warning(
                f"An error occurred while processing the summarize request: {str(e)}")
            logging.info("Retrying...")
            time.sleep(1)
            retry_count += 1

    return "Oops, something went wrong. Please try again later."


def analyze(user, chat_session):
    retry_count = 0
    while retry_count < 3:
        try:
            messages = [
                {"role": "system", "content": f"Perform a detailed analysis and summarize the key points from these messages and provide feedback for {user}. Provide actionable recommendations to improve their idea's effectiveness for the betterment of the Breeze Club Discord Server."},
                {"role": "assistant", "content": f"{chat_session}"},
            ]
            return llm_client.chat(
                messages, 
                request_type="analyze", 
                temperature=0.3, 
                max_tokens=3000,
                task_priority="normal"  # Background task: can use slower models
            )
        except Exception as e:
            logger.warning(
                f"An error occurred while processing the summarize request: {str(e)}")
            logger.info("Retrying...")
            time.sleep(1)
            retry_count += 1

    return "Oops, something went wrong. Please try again later."


# Note: chat_gpt4 (code mode) has been deprecated
# All conversations now use the unified chat() function with task_priority="high"
# This provides consistent, fast responses without mode switching complexity

