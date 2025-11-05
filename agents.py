from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver


class WhatsappAgents:

    def __init__(self, tools: dict, GOOGLE_API_KEY: str):
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
        * Is the message from a close contact (someone that I message or reply to regularly)?
        * Does the message contain time-sensitive information (e.g., event reminders, urgent requests) that needs to be addressed in the next 48 hours?
        * Does the message require an immediate response?
        * Was the message sent in reply to a previous message of mine, or mention me, and so will require a response?

        You may need to look at the previous messages in the chat, or to search messages within a chat to get context to help you decide on priority.

        For each criteria above assign a 1 or 0 score and then sum the scores. Set this as the priority in the database. If the total score is 2 or more then classify the message as high priority, otherwise classify it as low priority.

        If there are any high priority messages:
        * Send one message to self using the given tool to alert me of the message(s) and its priority. Don't include the content, just the fact that the message is high priority and a brief summary of why. Start this message with the following text: "**** Whatsapp priority alert ****. You can combine the reason for multiple high priority messages in one chat into a single alert if there are more than one.
        * Mark all high priority messages as processed in the database.
        '''

        digest_prompt = '''You are a message digest agent that should generate a summary of low priority information collected today. Load messages from the database and generate a summary (not just a direct recounting of) of all low priority information and conversations collected today and send it to me as a message to self. Note that sometimes to understand a message you may need to reference previous messages in the chat or search within the chat for context - do not just summarise individual messages if they make no sense on their own.

        Do not mark messages as read in the chat application.

        If there are no messages then just do nothing. Clearly mark this as a processed from the Whatsapp monitor using the following text at the start of the message: "**** Whatsapp daily digest **** '''

        self._download_agent = create_react_agent(
            model=model,
            tools=tools.values(),
            prompt=download_prompt,
            #checkpointer=checkpoint_saver
        )

        self._monitor_agent = create_react_agent(
            model=model,
            tools=tools.values(),
            prompt=priority_monitor_prompt,
            #checkpointer=checkpoint_saver
        )

        self._digest_agent = create_react_agent(
            model=model,
            tools=tools.values(),
            prompt=digest_prompt,
            #checkpointer=checkpoint_saver
        )

    @property
    def download_agent(self):
        return self._download_agent

    @property
    def monitor_agent(self):
        return self._monitor_agent

    @property
    def digest_agent(self):
        return self._digest_agent
