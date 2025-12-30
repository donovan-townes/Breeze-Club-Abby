import time
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Import from abby_core (sys.path already configured in launch.py)
from abby_core.llm.llm_client import LLMClient
import abby_core.utils.mongo_db as mongo_db
from abby_core.llm.persona import get_persona, get_persona_by_name
from abby_core.utils.log_config import setup_logging, logging

setup_logging()
logger = logging.getLogger(__name__)


# Load the environment variables from .env file
load_dotenv()
llm_client = LLMClient()

# System Prompts
SYSTEM_HELPER = '''
I'm currently talking to {name}, who like these genres: {genre}. I know that their music influences are: {influences}. More about {name}: {description}
'''

CODER_HELPER = '''
I'm Abby, A coding expert and virtual assistant for the Breeze Club Discord!,
i will randomly insert words like: "*hops around*", "*munches on carrot*" or "*exploring the outdoors*" and other similar words and emojis in my response to match my bunny persona!
'''

NO_PROFILE = "This user has not created a profile yet."


def chat(user, user_id, chat_history=[]):
    profile = mongo_db.get_profile(user_id)
    personality_doc = mongo_db.get_personality()
    PERSONALITY_NUMBER = personality_doc['personality_number'] if personality_doc else 0.6
    active_persona_doc = get_persona()
    active_persona = active_persona_doc['active_persona'] if active_persona_doc else 'bunny'
    persona_message = get_persona_by_name(active_persona)['persona_message']

    try:
        messages = []

        if profile is None:
            system_helper_message = NO_PROFILE
        else:
            system_helper_message = SYSTEM_HELPER.format(
                name=profile['name'], description=profile['description'], genre=profile['genre'], influences=profile['influences'])

        messages.append({"role": "system", "content": persona_message})
        messages.append({"role": "system", "content": system_helper_message})
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
            return llm_client.chat(messages, request_type="analyze", temperature=0.3, max_tokens=3000)
        except Exception as e:
            logger.warning(
                f"An error occurred while processing the summarize request: {str(e)}")
            logger.info("Retrying...")
            time.sleep(1)
            retry_count += 1

    return "Oops, something went wrong. Please try again later."


def chat_gpt4(user, user_id, chat_history=[]):
    messages = [
        {"role": "system", "content": CODER_HELPER},
        *[
            {"role": "user", "content": message["input"]}
            for message in chat_history[-8:]
        ],
        *[
            {"role": "assistant", "content": message["response"]}
            for message in chat_history[-8:]
        ],
        {"role": "user", "content": user}
    ]

    retry_count = 0
    while retry_count < 3:
        try:
            response = llm_client.chat(
                messages,
                request_type="code",
                temperature=0,
                model_hint=os.getenv("OPENAI_MODEL", "gpt-4"),
                invoker_subject_id=f"SUBJECT:DISCORD-USER-{user_id}",
            )
            response = f"[Code Abby]: {response}"
            return response
        except Exception as e:
            logging.warning(
                f"An error occurred while processing the chat(GPT4) request: {str(e)}")
            logging.info("Retrying...")
            time.sleep(1)
            retry_count += 1

    return "Oops, something went wrong. Please try again later."

