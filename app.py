from typing import Dict, Optional, Union

from autogen import Agent, AssistantAgent, UserProxyAgent, config_list_from_json
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent
import chainlit as cl
from market_researcher import *

welcome_message = """Welcome to the Market Research bot developed for LLMops3 Final Project !!!
- Provide the user message with user queries filled in an Airtable
- The `Research Director` bot will be using the `Airtable` Link to get the list of research objectives
- Then `Research Manager` bot will delegates and evalutes task from the `Market Research`
- The `Market Research` bot uses various tools like `DuckDuckGo Search`, `Browserless API` scraping and `Summarization` chain to do market research
"""

TASK = """
Research the funding stage/amount & pricing for each company in the list: https://airtable.com/app3j1GszyrlqvYXr/tblIkhp07k1GhfXB3/viwHhoh2vs14nJCrm?blocks=hide
"""
config_list = config_list_from_json(env_or_file="OAI_CONFIG_LIST")

async def ask_helper(func, **kwargs):
    res = await func(**kwargs).send()
    while not res:
        res = await func(**kwargs).send()
    return res


class ChainlitGPTAssistantAgent(GPTAssistantAgent):
    def send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ) -> bool:
        cl.run_sync(
            cl.Message(
                content=f'*Sending message to "{recipient.name}":*\n\n{message["content"]}',
                author="GPTAssistantAgent",
            ).send()
        )
        super(ChainlitGPTAssistantAgent, self).send(
            message=message,
            recipient=recipient,
            request_reply=request_reply,
            silent=silent,
        )



class ChainlitAssistantAgent(AssistantAgent):
    def send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ) -> bool:
        cl.run_sync(
            cl.Message(
                content=f'*Sending message to "{recipient.name}":*\n\n{message["content"]}',
                author="AssistantAgent",
            ).send()
        )
        super(ChainlitAssistantAgent, self).send(
            message=message,
            recipient=recipient,
            request_reply=request_reply,
            silent=silent,
        )


class ChainlitUserProxyAgent(UserProxyAgent):
    def get_human_input(self, prompt: str) -> str:
        if prompt.startswith(
            "Provide feedback to chat_manager. Press enter to skip and use auto-reply, or type 'exit' to end the conversation:"
        ):
            res = cl.run_sync(
                ask_helper(
                    cl.AskActionMessage,
                    content="Continue or provide feedback?",
                    actions=[
                        cl.Action(
                            name="continue", value="continue", label="✅ Continue"
                        ),
                        cl.Action(
                            name="feedback",
                            value="feedback",
                            label="💬 Provide feedback",
                        ),
                        cl.Action( 
                            name="exit",
                            value="exit", 
                            label="🔚 Exit Conversation" 
                        ),
                    ],
                )
            )
            if res.get("value") == "continue":
                return ""
            if res.get("value") == "exit":
                return "TERMINATE"

        reply = cl.run_sync(ask_helper(cl.AskUserMessage, content=prompt, timeout=60))

        return reply["content"].strip()

    def send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
    ):
        cl.run_sync(
            cl.Message(
                content=f'*Sending message to "{recipient.name}"*:\n\n{message}',
                author="UserProxyAgent",
            ).send()
        )
        super(ChainlitUserProxyAgent, self).send(
            message=message,
            recipient=recipient,
            request_reply=request_reply,
            silent=silent,
        )


@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content=welcome_message).send()

    await cl.Avatar(
        name="Chatbot",
        path="icon/chainlit.png"
        ).send()
    await cl.Avatar(
        name="AssistantAgent",
        path="icon/chainlit.png"
        ).send()
    await cl.Avatar(
        name="GPTAssistantAgent",
        path="icon/openai.png"
        ).send()
    
    await cl.Avatar(
        name="User",
        path="icon/avatar.png",
    ).send()
    await cl.Avatar(
        name="UserProxyAgent",
        path="icon/avatar.png",
    ).send()
    
    assistant = ChainlitAssistantAgent(
        "assistant", 
        llm_config={"config_list": config_list}
    )
    user_proxy = ChainlitUserProxyAgent(
        "user_proxy",
        code_execution_config={
            "work_dir": "workspace",
            "use_docker": False,
        },
        human_input_mode="ALWAYS",
        max_consecutive_auto_reply=1
    )
    
    market_researcher = ChainlitGPTAssistantAgent(
        "market_researcher",
        llm_config = {
        "config_list": config_list,
        "assistant_id": "asst_s8wJx1VWOgJOBZP3DCC23V3p"
    }
    )
    market_researcher.register_function(
    function_map={
        "web_scraping": web_scraping,
        "google_search": google_search
    }
    )
    
    # Create research manager agent
    research_manager = ChainlitGPTAssistantAgent(
        "research_manager",
        llm_config = {
            "config_list": config_list,
            "assistant_id": "asst_o6htPuVLrh9Pw1CBtaRYK3pQ"
        }
    )


    # Create research_director agent
    research_director = ChainlitGPTAssistantAgent(
        "research_director",
        llm_config = {
            "config_list": config_list,
            "assistant_id": "asst_RqSh4EkzVpsInu1V3FTiF7yq",
        }
    )

    research_director.register_function(
        function_map={
            "get_airtable_records": get_airtable_records,
            "update_single_airtable_record": update_single_airtable_record
        }
    )
    
    cl.user_session.set("research_director", research_director)
    cl.user_session.set("user_proxy", user_proxy)
    cl.user_session.set("assistant", assistant)
    cl.user_session.set("market_researcher", market_researcher)
    cl.user_session.set("research_manager", research_manager)


@cl.on_message
async def on_message(message: cl.Message):

    research_director = cl.user_session.get("research_director")
    user_proxy = cl.user_session.get("user_proxy")
    market_researcher = cl.user_session.get("market_researcher")
    research_manager = cl.user_session.get("research_manager")
    
    groupchat = autogen.GroupChat(agents=[user_proxy, market_researcher, research_manager, research_director], messages=[], max_round=15)
    group_chat_manager = autogen.GroupChatManager(groupchat=groupchat, llm_config={"config_list": config_list})
    
    
    #await cl.Message(content=f"Starting agents on task: {TASK}...").send()
    await cl.make_async(user_proxy.initiate_chat)(
        group_chat_manager,
        message=f"Starting agents on task: {message.content}...",
    )