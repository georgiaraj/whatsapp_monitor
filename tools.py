import requests
import sqlite3

from datetime import datetime


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
                          priority INTEGER DEFAULT 0,
                          processed INTEGER DEFAULT 0)''')
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
                           message: str, timestamp: str = None, processed: int = 0):
        '''Saves messages to the local SQLite database.
        Arguments:
        chat_id -- The ID of the chat
        message -- The message content
        timestamp -- The timestamp of the message (optional)
        processed -- Whether the message has been processed (either by alerting or including in digest))
        '''
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (chat_id, chat_name, message, timestamp, processed) "
                           "VALUES (?, ?, ?, ?, ?)", (chat_id, chat_name, message, timestamp, processed)
                           )
            conn.commit()

    def prioritise_message(self, message_id: int, priority: int):
        '''Sets the priority of a message in the local SQLite database.'''
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE messages SET priority = ? WHERE id = ?", (priority, message_id))
            conn.commit()

    def mark_message_as_processed(self, message_id: int):
        '''Marks a message as processed in the local SQLite database.'''
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE messages SET processed = 1 WHERE id = ?", (message_id,))
            conn.commit()

    def generate_unprocessed_messages(self):
        '''Generates a list of id, chat_name, message, timestamp for unprocessed messages from the local SQLite database.'''
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, chat_name, message, timestamp FROM messages WHERE processed = 0")
            rows = cursor.fetchall()
            # Mark messages as processed
            cursor.execute("UPDATE messages SET processed = 1 WHERE processed = 0")
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
            "send_message_to_self": self.send_message_to_self,
            "search_messages": self.search_messages,
            "save_message_to_db": self.save_message_to_db,
            "prioritise_message": self.prioritise_message,
            "mark_message_as_processed": self.mark_message_as_processed,
            "generate_unprocessed_messages": self.generate_unprocessed_messages
        }



class TestTools(Tools):

    def __init__(self, api_url, db_file):
        pass

    def get_user_info(self):
        return json.loads({
            "success": true,
            "data": {
                "name": "Test User",
                "number": "+1234567890",
                "wid": 100,
                "platform": "web"
            }
        })

    # Generate test data based on format from server.js

    def get_chats(self):
        return json.loads({
            "id": "chat1",
            "name": "Test Chat",
            "isGroup": false,
            "unreadCount": 2,
            "isReadOnly": false
        })
