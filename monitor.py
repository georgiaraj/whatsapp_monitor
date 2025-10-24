import os
import sys
import requests
import sqlite3

from datetime import datetime
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

db_file = "messages.db"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
print("Using Google API Key:", GOOGLE_API_KEY)
api_url = "http://localhost:3000/api"


def get_chats():
    '''Fetches the list of all chats from the API.'''
    response = requests.get(f"{api_url}/chats")
    response.raise_for_status()
    return response.json()

def get_unread_chats():
    '''Fetches the list of unread chats from the API.'''
    response = requests.get(f"{api_url}/unread-chats")
    response.raise_for_status()
    return response.json()

def get_unread_messages(chat_id):
    '''Fetches unread messages for a specific chat.'''
    response = requests.get(f"{api_url}/chats/{chat_id}/unread-messages")
    response.raise_for_status()
    return response.json()

def get_messages_from_chat(chat_id, limit=10):
    '''Fetches the latest messages from a specific chat.'''
    response = requests.get(f"{api_url}/chats/{chat_id}/messages", params={"limit": limit})
    response.raise_for_status()
    return response.json()

def get_unread_messages_from_chat(chat_id, limit=10):
    '''Fetches the latest unread messages from a specific chat.'''
    response = requests.get(f"{api_url}/chats/{chat_id}/unread-messages", params={"limit": limit})
    response.raise_for_status()
    return response.json()

def mark_chat_as_read(chat_id):
    '''Marks a specific chat as read.'''
    response = requests.post(f"{api_url}/chats/{chat_id}/mark-as-read")
    response.raise_for_status()
    return response.json()

def mark_all_chats_as_read():
    '''Marks all chats as read.'''
    response = requests.post(f"{api_url}/chats/mark-all-as-read")
    response.raise_for_status()
    return response.json()

def send_message(chat_id, message):
    '''Sends a message to a specific chat.'''
    payload = {"chat_id": chat_id, "message": message}
    response = requests.post(f"{api_url}/send-message", json=payload)
    response.raise_for_status()
    return response.json()

def send_message_to_self(message):
    '''Sends a message to oneself.'''
    payload = {"message": message}
    response = requests.post(f"{api_url}/send-message-to-self", json=payload)
    response.raise_for_status()
    return response.json()

def search_messages(query, limit=10):
    '''Searches messages containing a specific query.'''
    response = requests.get(f"{api_url}/search-messages", params={"query": query, "limit": limit})
    response.raise_for_status()
    return response.json()

def save_message_to_db(chat_id: str, chat_name: str,
                       message: str, timestamp: str = None, digest: int = 0):
    '''Saves messages to the local SQLite database.
    Arguments:
        chat_id -- The ID of the chat
        message -- The message content
        timestamp -- The timestamp of the message (optional)
        digest -- Whether the message has been included in a digest (0 or 1)
    '''
    if timestamp is None:
        timestamp = datetime.now().isoformat()

    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (chat_id, chat_name, message, timestamp, digest) "
                       "VALUES (?, ?, ?, ?, ?)", (chat_id, chat_name, message, timestamp, digest)
                       )
        conn.commit()

def generate_digest_messages():
    '''Generates a list of messages and timestamps not already marked as digest.'''
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_name, message, timestamp FROM messages WHERE digest = 0")
        rows = cursor.fetchall()
        # Mark messages as digest
        cursor.execute("UPDATE messages SET digest = 1 WHERE digest = 0")
        conn.commit()
        return rows


tools = {
    "get_chats": get_chats,
    "get_unread_chats": get_unread_chats,
    "get_unread_messages": get_unread_messages,
    "get_messages_from_chat": get_messages_from_chat,
    "get_unread_messages_from_chat": get_unread_messages_from_chat,
    "mark_chat_as_read": mark_chat_as_read,
    "mark_all_chats_as_read": mark_all_chats_as_read,
    "send_message_to_self": send_message_to_self,
    "search_messages": search_messages,
    "save_message_to_db": save_message_to_db,
    "generate_digest_messages": generate_digest_messages
}


if __name__ == "__main__":

    #checkpoint_saver = InMemorySaver()

    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS messages
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           chat_id TEXT,
                           chat_name TEXT,
                           message TEXT,
                           timestamp TEXT,
                           digest INTEGER DEFAULT 0)''')
        conn.commit()

    model = init_chat_model(
        model="gemini-2.5-flash",
        model_provider="google_genai",
        api_key=GOOGLE_API_KEY
    )
    monitor_prompt = '''You are a message monitor agent that should check for new messages in chats.

    If you notice messages that are directly to me, or in group chats but appear to be important to action, you should notify me by sending a message to self. Rather than including the full message, please tell me which group chat to look at. If a direct message, then please send me the link to the whatsapp chat so that I can read and action the message myself. Please mark this message as coming from the Whatsapp monitor, but ensure that it details the person who sent the message and the content of the message. Use this text at the start of the message: "**** Whatsapp monitor alert ****".

    For some messages, particularly in group chats, you might need more context to decide if something is important. In such cases, you should get previous messages from the chat, or search withing the chat, to get a better understanding of the conversation before deciding whether to alert me.

    You should also store all messages you see in a local database for future reference. Mark the ones that have already be sent in the alert using the digest argument so that they are not included in a future digest.

    Do not mark messages as read in the chat application unless explicitly told to do so. Only alert me of priority messages; do not alert me of low priority information.
    '''

    digest_prompt = '''You are a message digest agent that should generate a summary of low priority information collected today. Load messages from the database and generate a summary (not just a direct recounting of) of all low priority information and conversations collected today and send it to me as a message to self. Note that sometimes to understand a message you may need to reference previous messages in the chat or search within the chat for context.

    If there are no messages then just do nothing. Clearly mark this as a digest from the Whatsapp monitor using the following text at the start of the message: "**** Whatsapp daily digest **** '''

    monitor = create_react_agent(
        model=model,
        tools=tools.values(),
        prompt=monitor_prompt,
        #checkpointer=checkpoint_saver
    )

    digest_agent = create_react_agent(
        model=model,
        tools=tools.values(),
        prompt=digest_prompt,
        #checkpointer=checkpoint_saver
    )

    # Test the db functions
    # save_info_to_db(1, "Test message 1")
    # save_info_to_db(2, "Test message 2")
    # digest_info = generate_digest_info()

    # print("Digest info:", digest_info)

    # sys.exit()

    response = monitor.invoke({
        "messages": [
            {"role": "user", "content": "Check for new messages."}
        ]
    }, config={"recursion_limit": 50})

    print(response['messages'][-1].content)

    response = digest_agent.invoke({
        "messages": [
            {"role": "user", "content": "Generate a digest of low priority information collected today and send as a message to self."}
        ]
    })

    print(response['messages'][-1].content)
