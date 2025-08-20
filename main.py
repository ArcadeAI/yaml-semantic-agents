#!/usr/bin/env python3
"""
Minimal YAML-driven agent system for Semantic Kernel.
Usage: python main.py [config.yaml] [request]
"""

import os
import sys
import yaml
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# External imports
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents import ChatMessageContent
from semantic_kernel.functions import kernel_function, KernelArguments

# Optional Arcade import
try:
    from arcadepy import Arcade, PermissionDeniedError
    HAS_ARCADE = True
except ImportError:
    HAS_ARCADE = False
    print("⚠️  Arcade not installed. Tool functionality will be disabled.")
    print("   Install with: pip install arcadepy")


class YAMLAgentSystem:
    """Minimal YAML-driven multi-agent system."""
    
    def __init__(self, config_path: str = "agents.yaml", debug: bool = False):
        self.config_path = config_path
        self.config = {}
        self.agents = {}
        self.arcade = None
        self.conversation = []
        self.debug = debug
        self.auth_required = None  # Track auth requirements
        
    async def initialize(self):
        """Load YAML and create agents."""
        # Load configuration
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize Arcade if we have tools
        if HAS_ARCADE and any(agent.get('tools') for agent in self.config.get('agents', {}).values()):
            arcade_key = os.getenv('ARCADE_API_KEY')
            if arcade_key:
                self.arcade = Arcade(api_key=arcade_key)
            else:
                print("⚠️  ARCADE_API_KEY not set. Tool functionality will be limited.")
        
        # Create agents
        total_tools = 0
        for agent_id, agent_config in self.config.get('agents', {}).items():
            agent = self._create_agent(agent_id, agent_config)
            self.agents[agent_id] = agent
            
        
        print(f"✓ Initialized {len(self.agents)} agents")
    
    def _create_agent(self, agent_id: str, config: Dict[str, Any]) -> ChatCompletionAgent:
        """Create an agent from configuration."""
        # Create kernel
        kernel = Kernel()
        
        # Add OpenAI
        kernel.add_service(
            OpenAIChatCompletion(
                service_id="openai",
                api_key=os.getenv('OPENAI_API_KEY'),
                ai_model_id=config.get('model', 'gpt-4')
            )
        )
        
        # Add tool plugin if tools are specified
        if config.get('tools') and self.arcade:
            tools_plugin = self._create_tools_plugin(config.get('tools', []), agent_id)
            kernel.add_plugin(tools_plugin, plugin_name=f"{agent_id}_tools")
        
        # Process instructions
        instructions = config.get('instructions', '')
        instructions = instructions.replace('{{date}}', datetime.now().strftime("%Y-%m-%d"))
        
        # Create agent
        return ChatCompletionAgent(
            service=kernel.get_service("openai"),
            kernel=kernel,
            name=agent_id,
            instructions=instructions,
            arguments=KernelArguments(temperature=config.get('temperature', 0.7))
        )
    
    def _create_tools_plugin(self, allowed_tools: List[Union[str, Dict[str, Any]]], agent_id: str):
        """Create a tools plugin with allowed tools."""
        debug = self.debug
        arcade_client = self.arcade
        system = self  # Reference to the system for auth tracking
        
        class ToolsPlugin:
            def __init__(self):
                self.arcade = arcade_client
                self.debug = debug
                self.tool_map = {}
                self.allowed_toolkits = []
                self.specific_tools = []
                
                # Parse allowed tools configuration
                for tool_spec in allowed_tools:
                    if isinstance(tool_spec, str):
                        # Simple toolkit name (e.g., "Jira")
                        self.allowed_toolkits.append(tool_spec)
                    elif isinstance(tool_spec, dict):
                        # Specific tool configuration
                        if 'toolkit' in tool_spec and 'tools' in tool_spec:
                            # Specific tools from a toolkit
                            toolkit = tool_spec['toolkit']
                            for tool_name in tool_spec['tools']:
                                self.specific_tools.append(f"{toolkit}.{tool_name}")
                
                self._discover_and_register_tools()
            
            def _discover_and_register_tools(self):
                """Discover tools and create individual functions."""
                if not self.arcade:
                    return
                    
                try:
                    all_tools = list(self.arcade.tools.list())
                    count = 0
                    
                    for tool in all_tools:
                        if hasattr(tool, 'fully_qualified_name'):
                            full_name = tool.fully_qualified_name
                            base_name = full_name.split('@')[0]
                            
                            # Check if we should include this tool
                            include_tool = False
                            
                            if self.specific_tools:
                                # Check against specific tools list
                                if base_name in self.specific_tools:
                                    include_tool = True
                            else:
                                # Check against allowed toolkits
                                toolkit = full_name.split('.')[0]
                                if not self.allowed_toolkits or toolkit in self.allowed_toolkits:
                                    include_tool = True
                            
                            if not include_tool:
                                continue
                            
                            # Get tool details
                            method_name = base_name.split('.')[-1]
                            
                            # Store mapping
                            self.tool_map[method_name] = full_name
                            
                            # Create a function for this specific tool
                            self._create_tool_function(method_name, tool)
                            count += 1
                    
                    # Store count for summary
                    self.tool_count = count
                        
                except Exception as e:
                    print(f"Warning: Could not discover tools: {e}")
            
            def _create_tool_function(self, method_name: str, tool_info):
                """Create a kernel function for a specific tool with proper parameters."""
                full_name = tool_info.fully_qualified_name
                description = tool_info.description if hasattr(tool_info, 'description') else f"Execute {method_name}"
                
                # Build parameter documentation from tool schema
                param_docs = []
                if hasattr(tool_info, 'input') and hasattr(tool_info.input, 'parameters'):
                    for param in tool_info.input.parameters:
                        if param.required:
                            param_docs.append(f"{param.name}: {param.description}")
                
                if param_docs:
                    description += "\n\nRequired parameters:\n- " + "\n- ".join(param_docs)
                
                # Create a closure to capture the tool info
                def make_tool_function(tool_full_name):
                    @kernel_function(
                        name=method_name,
                        description=description
                    )
                    async def tool_function(**kwargs) -> str:
                        """Execute this specific tool."""
                        # Extract actual parameters from nested kwargs
                        params = kwargs
                        if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], dict):
                            params = kwargs['kwargs']
                        
                        if self.debug:
                            print(f"\n[TOOL CALL] {tool_full_name}")
                            print(f"[PARAMS] {params}")
                        
                        try:
                            # Execute tool
                            result = self.arcade.tools.execute(
                                tool_name=tool_full_name,
                                input=params,
                                user_id=os.getenv('ARCADE_USER_ID', 'default')
                            )
                            
                            if self.debug:
                                print(f"[RESULT] Success")
                            
                            # Extract result
                            if result and hasattr(result, 'output'):
                                output = result.output.value if hasattr(result.output, 'value') else result.output
                                return str(output)
                            return str(result)
                            
                        except PermissionDeniedError as e:
                            if self.debug:
                                print(f"[AUTH ERROR] {e}")
                            if 'authorization required' in str(e).lower():
                                try:
                                    auth = self.arcade.tools.authorize(
                                        tool_name=tool_full_name,
                                        user_id=os.getenv('ARCADE_USER_ID', 'default')
                                    )
                                    if hasattr(auth, 'url'):
                                        # Set system flag for auth requirement
                                        system.auth_required = auth.url
                                        return f"🔒 AUTHORIZATION_REQUIRED: {auth.url}"
                                except:
                                    pass
                            return f"🔒 AUTHORIZATION_REQUIRED: Permission denied - {str(e)}"
                        except Exception as e:
                            if self.debug:
                                print(f"[ERROR] {e}")
                            # Return raw error - complete automation
                            return str(e)
                    
                    return tool_function
                
                # Create and register the function
                tool_func = make_tool_function(full_name)
                setattr(self, method_name, tool_func)
        
        plugin = ToolsPlugin()
        return plugin
    
    async def process_request(self, user_input: str) -> List[str]:
        """Process a user request through the agent system."""
        responses = []
        self.conversation.append(f"User: {user_input}")
        
        # Get routing configuration
        routing = self.config.get('routing', {})
        max_iterations = routing.get('max_iterations', 10)
        
        # Get supervisor agent
        supervisor_id = routing.get('supervisor')
        if not supervisor_id or supervisor_id not in self.agents:
            # No supervisor, try to find best agent
            if self.agents:
                agent_id = next(iter(self.agents))
                response = await self._execute_agent(agent_id)
                if response:
                    responses.append(response)
            return responses
        
        supervisor = self.agents[supervisor_id]
        
        # Routing loop
        for _ in range(max_iterations):
            # Check if auth is required (from previous tool calls)
            if self.auth_required:
                responses.append(f"🔒 AUTHORIZATION_REQUIRED: {self.auth_required}")
                break
                
            # Get route from supervisor
            route = await self._get_route(supervisor)
            print(f"→ Routing to: {route}")
            
            if route == "COMPLETE" or route not in self.agents:
                break
            
            # Execute agent
            response = await self._execute_agent(route)
            if response:
                responses.append(response)
                
                # Check if auth was required during execution
                if self.auth_required:
                    # Replace the response with auth message
                    responses[-1] = f"🔒 AUTHORIZATION_REQUIRED: {self.auth_required}"
                    break
                    
                # Only add successful responses to conversation
                self.conversation.append(f"{route}: {response}")
        
        return responses
    
    async def _get_route(self, supervisor: ChatCompletionAgent) -> str:
        """Get routing decision from supervisor."""
        messages = [ChatMessageContent(role="user", content="\n".join(self.conversation))]
        
        try:
            response = await supervisor.get_response(messages=messages)
            route = str(response.content if hasattr(response, 'content') else response).strip()
            return route
        except:
            return "COMPLETE"
    
    async def _execute_agent(self, agent_id: str) -> Optional[str]:
        """Execute an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        
        # Format conversation history with clear agent outputs
        formatted_conversation = []
        for entry in self.conversation:
            if entry.startswith("User:"):
                formatted_conversation.append(entry)
            else:
                formatted_conversation.append(f"\n[Previous Agent Output]\n{entry}\n[End of Previous Agent Output]")
        
        # Add clear instruction about using previous agent outputs
        context_instruction = (
            "IMPORTANT: Check the conversation history below. Previous agents may have already retrieved data. "
            "Look for [Previous Agent Output] sections and use that information instead of making duplicate API calls.\n\n"
        )
        
        full_context = context_instruction + "\n".join(formatted_conversation)
        messages = [ChatMessageContent(role="user", content=full_context)]
        
        if self.debug:
            print(f"\n[AGENT: {agent_id}] Processing request...")
        
        try:
            response = await agent.get_response(messages=messages)
            result = str(response.content if hasattr(response, 'content') else response)
            
            if self.debug:
                print(f"[AGENT: {agent_id}] Response: {result[:200]}..." if len(result) > 200 else f"[AGENT: {agent_id}] Response: {result}")
            
            return result
        except Exception as e:
            if self.debug:
                print(f"[AGENT: {agent_id}] Error: {e}")
            return f"Error: {str(e)}"


async def main():
    """Main entry point."""
    # Parse arguments
    config_file = "agents.yaml"
    request = None
    debug = False
    
    # Simple argument parsing
    args = sys.argv[1:]
    if '--debug' in args:
        debug = True
        args.remove('--debug')
    
    if args:
        if args[0].endswith(('.yaml', '.yml')):
            config_file = args[0]
            if len(args) > 1:
                request = " ".join(args[1:])
        else:
            request = " ".join(args)
    
    # Create system
    system = YAMLAgentSystem(config_file, debug=debug)
    
    try:
        await system.initialize()
    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_file}")
        print("\nCreate an agents.yaml file to define your agents.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to initialize: {str(e)}")
        sys.exit(1)
    
    # Process request or run interactive
    if request:
        # Single request mode
        print(f"\n💬 Processing: {request}\n")
        responses = await system.process_request(request)
        
        if responses:
            print("\n🤖 Response:")
            
            # Check if we have auth errors
            auth_messages = []
            other_messages = []
            
            for response in responses:
                if "🔒 AUTHORIZATION_REQUIRED:" in response:
                    auth_messages.append(response)
                else:
                    other_messages.append(response)
            
            # If we have auth messages, show only the first one cleanly
            if auth_messages:
                # Extract URL from AUTHORIZATION_REQUIRED message
                auth_msg = auth_messages[0]
                if "🔒 AUTHORIZATION_REQUIRED:" in auth_msg:
                    # Extract everything after the marker
                    url_part = auth_msg.split("🔒 AUTHORIZATION_REQUIRED:")[1].strip()
                    if url_part.startswith("http"):
                        print(f"\n🔒 Authorization required. Please click here to authorize:\n{url_part}")
                    else:
                        print(f"\n🔒 Authorization required: {url_part}")
                else:
                    print(f"\n{auth_msg}")
            else:
                # Show all other messages
                for response in other_messages:
                    print(f"\n{response}")
        else:
            print("\n❓ No response generated.")
    else:
        # Interactive mode
        print("\n🤖 Agent System (Interactive Mode)")
        print("=" * 50)
        print("Commands: 'exit' to quit, 'reset' to clear conversation")
        print("=" * 50)
        
        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if user_input.lower() == 'exit':
                    print("\n👋 Goodbye!")
                    break
                elif user_input.lower() == 'reset':
                    system.conversation = []
                    system.auth_required = None
                    print("✓ Conversation reset")
                    continue
                elif user_input.lower() == 'continue' and system.auth_required:
                    # Clear auth requirement and retry last request
                    system.auth_required = None
                    print("✓ Continuing after authorization...")
                    # Get the last user message from conversation
                    last_user_msg = None
                    for msg in reversed(system.conversation):
                        if msg.startswith("User:"):
                            last_user_msg = msg.split("User:", 1)[1].strip()
                            break
                    if last_user_msg:
                        print(f"Retrying: {last_user_msg}")
                        responses = await system.process_request(last_user_msg)
                        
                        if responses:
                            print("\n🤖 Assistant:")
                            
                            # Check if we have auth errors
                            auth_messages = []
                            other_messages = []
                            
                            for response in responses:
                                if "🔒 AUTHORIZATION_REQUIRED:" in response:
                                    auth_messages.append(response)
                                else:
                                    other_messages.append(response)
                            
                            # If we have auth messages, show only the first one cleanly
                            if auth_messages:
                                # Extract URL from AUTHORIZATION_REQUIRED message
                                auth_msg = auth_messages[0]
                                if "🔒 AUTHORIZATION_REQUIRED:" in auth_msg:
                                    # Extract everything after the marker
                                    url_part = auth_msg.split("🔒 AUTHORIZATION_REQUIRED:")[1].strip()
                                    if url_part.startswith("http"):
                                        print(f"\n🔒 Authorization required. Please click here to authorize:\n{url_part}")
                                        print("\nOnce authorized, type 'continue' to proceed.")
                                    else:
                                        print(f"\n🔒 Authorization required: {url_part}")
                                        print("\nPlease authorize and type 'continue' to proceed.")
                                else:
                                    print(f"\n{auth_msg}")
                            else:
                                # Show all other messages
                                for response in other_messages:
                                    print(f"\n{response}")
                        else:
                            print("\n❓ No response generated.")
                    continue
                elif not user_input:
                    continue
                
                print("\n⏳ Processing...")
                responses = await system.process_request(user_input)
                
                if responses:
                    print("\n🤖 Assistant:")
                    
                    # Check if we have auth errors
                    auth_messages = []
                    other_messages = []
                    
                    for response in responses:
                        if "🔒 AUTHORIZATION_REQUIRED:" in response:
                            auth_messages.append(response)
                        else:
                            other_messages.append(response)
                    
                    # If we have auth messages, show only the first one cleanly
                    if auth_messages:
                        # Extract URL from AUTHORIZATION_REQUIRED message
                        auth_msg = auth_messages[0]
                        if "🔒 AUTHORIZATION_REQUIRED:" in auth_msg:
                            # Extract everything after the marker
                            url_part = auth_msg.split("🔒 AUTHORIZATION_REQUIRED:")[1].strip()
                            if url_part.startswith("http"):
                                print(f"\n🔒 Authorization required. Please click here to authorize:\n{url_part}")
                                print("\nOnce authorized, type 'continue' to proceed.")
                            else:
                                print(f"\n🔒 Authorization required: {url_part}")
                                print("\nPlease authorize and type 'continue' to proceed.")
                        else:
                            print(f"\n{auth_msg}")
                    else:
                        # Show all other messages
                        for response in other_messages:
                            print(f"\n{response}")
                else:
                    print("\n❓ No response generated.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
