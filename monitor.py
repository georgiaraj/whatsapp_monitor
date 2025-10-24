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

class Tools:

    def __init__(self, api_url, db_file):
        self.api_url = api_url
        self.db_file = db_file

        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS messages
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          chat_id TEXT,
                          chat_name TEXT,
                          message TEXT,
                          timestamp TEXT,
                          digest INTEGER DEFAULT 0)''')
            conn.commit()

    def get_user_info(self):
        '''Fetches user information from the API.'''
        response = requests.get(f"{self.api_url}/user-info")
        response.raise_for_status()
        return response.json()

    def get_chats(self):
        '''Fetches the list of all chats from the API.'''
        response = requests.get(f"{self.api_url}/chats")
        response.raise_for_status()
        return response.json()

    def get_unread_chats(self):
        '''Fetches the list of unread chats from the API.'''
        response = requests.get(f"{self.api_url}/unread-chats")
        response.raise_for_status()
        return response.json()

    def get_unread_messages(self):
        '''Fetches unread messages for a specific chat.'''
        response = requests.get(f"{self.api_url}/chats/{chat_id}/unread-messages")
        response.raise_for_status()
        return response.json()

    def get_messages_from_chat(self, chat_id, limit=10):
        '''Fetches the latest messages from a specific chat.'''
        response = requests.get(f"{self.api_url}/chats/{chat_id}/messages", params={"limit": limit})
        response.raise_for_status()
        return response.json()

    def get_unread_messages_from_chat(self, chat_id, limit=10):
        '''Fetches the latest unread messages from a specific chat.'''
        response = requests.get(f"{self.api_url}/chats/{chat_id}/unread-messages", params={"limit": limit})
        response.raise_for_status()
        return response.json()

    def mark_chat_as_read(self, chat_id):
        '''Marks a specific chat as read.'''
        response = requests.post(f"{self.api_url}/chats/{chat_id}/mark-as-read")
        response.raise_for_status()
        return response.json()

    def mark_all_chats_as_read(self, ):
        '''Marks all chats as read.'''
        response = requests.post(f"{self.api_url}/chats/mark-all-as-read")
        response.raise_for_status()
        return response.json()

    def send_message(self, chat_id, message):
        '''Sends a message to a specific chat.'''
        payload = {"chat_id": chat_id, "message": message}
        response = requests.post(f"{self.api_url}/send-message", json=payload)
        response.raise_for_status()
        return response.json()

    def send_message_to_self(self, message):
        '''Sends a message to oneself.'''
        payload = {"message": message}
        response = requests.post(f"{self.api_url}/send-message-to-self", json=payload)
        response.raise_for_status()
        return response.json()

    def search_messages(self, query, limit=10):
        '''Searches messages containing a specific query.'''
        response = requests.get(f"{self.api_url}/search-messages", params={"query": query, "limit": limit})
        response.raise_for_status()
        return response.json()

    def save_message_to_db(self, chat_id: str, chat_name: str,
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

        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (chat_id, chat_name, message, timestamp, digest) "
                           "VALUES (?, ?, ?, ?, ?)", (chat_id, chat_name, message, timestamp, digest)
                           )
            conn.commit()

    def generate_digest_messages(self):
        '''Generates a list of messages and timestamps not already marked as digest.'''
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_name, message, timestamp FROM messages WHERE digest = 0")
            rows = cursor.fetchall()
            # Mark messages as digest
            cursor.execute("UPDATE messages SET digest = 1 WHERE digest = 0")
            conn.commit()

        return rows

    def tools(self):
        return {
            "get_user_info": self.get_user_info,
            "get_chats": self.get_chats,
            "get_unread_chats": self.get_unread_chats,
            "get_unread_messages": self.get_unread_messages,
            "get_messages_from_chat": self.get_messages_from_chat,
            "get_unread_messages_from_chat": self.get_unread_messages_from_chat,
            "mark_chat_as_read": self.mark_chat_as_read,
            "mark_all_chats_as_read": self.mark_all_chats_as_read,
            "send_message": self.send_message,
            "send_message_to_self": self.send_message_to_self,
            "search_messages": self.search_messages,
            "save_message_to_db": self.save_message_to_db,
            "generate_digest_messages": self.generate_digest_messages
        }


if __name__ == "__main__":

    #checkpoint_saver = InMemorySaver()
    tools = Tools(api_url=api_url, db_file=db_file).tools()

    model = init_chat_model(
        model="gemini-2.5-flash",
        model_provider="google_genai",
        api_key=GOOGLE_API_KEY
    )
    download_prompt = '''You are a message download agent that should check for new messages in chats.
    You should store all unread messages you see in a local database for future reference.

    Do not mark messages as read in the chat application.
    '''

    priority_monitor_prompt = '''You are a message priority monitor agent that should load the unread messages from the database and assess their priority.

    You should then prioritise the messages based on urgency and importance. To do this for each one you should consider the following criteria:
    * Is the message from a close contact (family, friend, work colleague)?
    * Does the message contain time-sensitive information (e.g., event reminders, urgent requests)?
    * Does the message require an immediate response?
    * Was the message sent in reply to a previous message of mine, or mention me, and so will require a response?

    You may need to look at the previous messages in the chat, or to search messages within a chat to get context to help you decide on priority.

    For each criteria above assign a 1 or 0 score and then sum the scores. If the total score is 2 or more then classify the message as high priority, otherwise classify it as low priority.

    If there are any high priority messages:
    * Send one message to self using the given tool to alert me of the message(s) and its priority. Don't include the content, just the fact that the message is high priority and a brief summary of why. Start this message with the following text: "**** Whatsapp priority alert ****. You can combine the reason for multiple high priority messages in one chat into a single alert if there are more than one.
    * Mark all high priority messages as digest in the database.
    '''

    digest_prompt = '''You are a message digest agent that should generate a summary of low priority information collected today. Load messages from the database and generate a summary (not just a direct recounting of) of all low priority information and conversations collected today and send it to me as a message to self. Note that sometimes to understand a message you may need to reference previous messages in the chat or search within the chat for context - do not just summarise individual messages if they make no sense on their own.

    Do not mark messages as read in the chat application.

    If there are no messages then just do nothing. Clearly mark this as a digest from the Whatsapp monitor using the following text at the start of the message: "**** Whatsapp daily digest **** '''

    download_agent = create_react_agent(
        model=model,
        tools=tools.values(),
        prompt=download_prompt,
        #checkpointer=checkpoint_saver
    )

    monitor_agent = create_react_agent(
        model=model,
        tools=tools.values(),
        prompt=priority_monitor_prompt,
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

    response = download_agent.invoke({
        "messages": [
            {"role": "user", "content": "Check for new messages."}
        ]
    }, config={"recursion_limit": 50})

    response = monitor_agent.invoke({
        "messages": [
            {"role": "user", "content": "Check for new messages."}
        ]
    }, config={"recursion_limit": 50})

    print(response['messages'][-1].content)

    # response = digest_agent.invoke({
    #     "messages": [
    #         {"role": "user", "content": "Generate a digest of low priority information collected today and send as a message to self."}
    #     ]
    # })

    #print(response['messages'][-1].content)
