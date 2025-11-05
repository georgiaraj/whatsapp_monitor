import os
import sys

from dotenv import load_dotenv

from tools import Tools
from agents import WhatsappAgents


load_dotenv()

db_file = "messages.db"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
print("Using Google API Key:", GOOGLE_API_KEY)
api_url = "http://localhost:3000/api"


if __name__ == "__main__":

    download = True
    prioritise = True
    create_digest = True

    #checkpoint_saver = InMemorySaver()
    tools = Tools(api_url=api_url, db_file=db_file).tools()

    agents = WhatsappAgents(tools=tools, GOOGLE_API_KEY=GOOGLE_API_KEY)

    if download:
        response = agents.download_agent.invoke({
            "messages": [
                {"role": "user", "content": "Check for new messages."}
            ]
        }, config={"recursion_limit": 50})

        print(response['messages'][-1].content)

    if prioritise:
        messages = tools['generate_unprocessed_messages']()
        for msg in messages:
            response = agents.monitor_agent.invoke({
                "messages": [
                    {"role": "user", "content": "Prioritise message {msg}."}
                ]
            }, config={"recursion_limit": 50})

        print(response['messages'][-1].content)

    if create_digest:
        response = agents.digest_agent.invoke({
            "messages": [
                {"role": "user", "content": "Generate a digest of unprocessed messages in the database, summarise and send as a message to self."}
            ]
        })

        print(response['messages'][-1].content)
