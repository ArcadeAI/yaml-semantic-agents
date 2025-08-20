# YAML-Driven Agent System

A powerful yet simple multi-agent system using Microsoft Semantic Kernel where you define everything in YAML. No coding required!

## Features

- **Pure YAML Configuration**: Define agents, prompts, tools, and routing in YAML
- **Automatic Agent Creation**: Agents are created from your YAML definitions using Semantic Kernel
- **Automatic Tool Discovery**: Agents automatically discover and learn how to use Arcade tools
- **Smart Tool Usage**: Tools are dynamically converted to Semantic Kernel functions - agents figure out parameters
- **Advanced Tool Filtering**: Support for toolkit-wide or specific tool permissions per agent
- **OAuth Authorization**: Built-in handling for tool authorization with 'continue' command
- **Conversation Context**: Agents see previous agent outputs to avoid duplicate API calls
- **Flexible Routing**: Define your own supervisor logic in YAML with configurable iterations
- **Debug Mode**: See tool discovery, calls, and agent processing with --debug flag
- **Interactive & Batch Modes**: Run interactively or process single requests
- **Minimal Code**: Just one Python file (556 lines) does everything

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment** (copy env.example to .env):
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

3. **Create your agents** (see templates):
   ```bash
   cp agents-template.yaml agents.yaml
   # Edit agents.yaml to define your agents
   ```

4. **Run the system**:
   ```bash
   # Interactive mode
   python main.py
   
   # Interactive mode with debug output
   python main.py --debug
   
   # Use specific config
   python main.py my-agents.yaml
   
   # Single request
   python main.py "What is the status of ticket ABC-123?"
   
   # Single request with specific config
   python main.py my-agents.yaml "Help me with this issue"
   
   # Debug mode with any command
   python main.py --debug agents.yaml "Get my Jira tickets"
   ```

## Interactive Mode Commands

When running interactively, you have these commands available:
- **Type your request**: Process through the agent system
- **`exit`**: Quit the system
- **`reset`**: Clear conversation history and auth state
- **`continue`**: Retry after completing OAuth authorization

## How It Works

1. **Define agents in YAML**:
   ```yaml
   agents:
     helper:
       instructions: |
         You are a helpful assistant.
         Answer questions clearly and concisely.
       tools:
         - Calculator  # All Calculator tools available
         - Jira       # All Jira tools available
   ```

2. **Advanced Tool Filtering**:
   ```yaml
   agents:
     specialist:
       instructions: Your specialized agent instructions
       tools:
         # Option 1: Allow entire toolkit
         - Jira
         
         # Option 2: Allow specific tools only
         - toolkit: Jira
           tools:
             - CreateIssue
             - GetIssue
             - UpdateIssue
   ```

3. **Add a supervisor** (optional):
   ```yaml
   agents:
     supervisor:
       instructions: |
         Route requests to the right agent:
         - helper: for general questions
         - specialist: for specific tasks
         - COMPLETE: when done
         
         Respond with ONLY the agent ID.
   
   routing:
     supervisor: supervisor
     max_iterations: 5
   ```

4. **Automatic Tool Discovery & Registration**:
   - When you specify tools, the system queries Arcade for available tools
   - Each tool is dynamically converted to a Semantic Kernel function
   - Tool parameters are extracted from Arcade schemas automatically
   - Agents learn how to use tools from their descriptions - no manual instructions needed
   - Tools are registered as native kernel functions for optimal performance

5. **Conversation Context Management**:
   - All agents see the full conversation history
   - Previous agent outputs are clearly marked to avoid duplicate API calls
   - Example: If Agent1 already fetched Jira tickets, Agent2 will see and use that data
   - System adds instructions to check for existing data before making new calls

6. **OAuth Authorization Flow**:
   - When a tool requires authorization, the system catches it automatically
   - Shows authorization URL to the user
   - User completes OAuth in browser
   - Type `continue` to retry the request with authorization
   - System maintains auth state across the conversation

7. **How the System Executes**:
   - Reads your YAML configuration
   - Creates Semantic Kernel agents with OpenAI integration
   - Discovers and registers Arcade tools as kernel functions
   - Routes requests through supervisor (if configured)
   - Manages conversation history and auth state
   - Handles errors gracefully with detailed feedback

## Examples

### Simple Single Agent
```yaml
agents:
  assistant:
    instructions: |
      You are a helpful AI assistant.
      Answer questions and help with tasks.
```

### Multi-Agent with Routing
```yaml
agents:
  researcher:
    instructions: Search and summarize information
    tools: [WebSearch]
  
  writer:
    instructions: Write and edit content
  
  supervisor:
    instructions: |
      Route to:
      - researcher: for finding information
      - writer: for creating content
      - COMPLETE: when done

routing:
  supervisor: supervisor
```

### IT Helpdesk System
See `it-helpdesk.yaml` for a complete example with:
- Ticket management (Jira)
- Knowledge search (SharePoint)
- Escalation (Email, Teams)

### Advanced Tool Configuration
```yaml
agents:
  data_analyst:
    instructions: Analyze and process data requests
    model: gpt-4
    temperature: 0.3
    tools:
      # Mix of full toolkit and specific tools
      - Calculator
      - toolkit: Jira
        tools:
          - GetIssue
          - SearchIssues
      - toolkit: SharePoint
        tools:
          - SearchDocuments
```

### Template Variables in Instructions
```yaml
agents:
  daily_assistant:
    instructions: |
      You are a daily planning assistant.
      Today's date is {{date}}.
      Help users plan their day and manage tasks.
```

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐     ┌─────────────────┐
│ agents.yaml │ ──> │              main.py                 │ ──> │  Agent System   │
│ (You write) │     │                                      │     │ (Auto-created)  │
└─────────────┘     │  1. YAMLAgentSystem loads config     │     └─────────────────┘
                    │  2. Creates Semantic Kernel agents   │              │
                    │  3. Discovers & registers tools      │              ▼
                    │  4. Manages conversation flow        │    ┌─────────────────┐
                    │  5. Handles auth & errors            │    │   Arcade API    │
                    └──────────────────────────────────────┘    │  (Tool access)  │
                                                                └─────────────────┘
```

### Internal Flow:
1. **YAML Loading**: Configuration parsed into agent definitions
2. **Agent Creation**: Each agent gets its own Semantic Kernel instance with OpenAI
3. **Tool Discovery**: Arcade tools are queried and filtered based on YAML permissions
4. **Dynamic Functions**: Tools become native Semantic Kernel functions via closures
5. **Routing Loop**: Supervisor decides which agent handles each step
6. **Context Propagation**: Full conversation history passed to each agent

## Environment Variables

- `OPENAI_API_KEY`: Required for agent LLMs
- `ARCADE_API_KEY`: Optional, for tool access
- `ARCADE_USER_ID`: Optional, for tool access

## Tips

1. **Start simple**: One agent, no routing
2. **Use debug mode**: Add `--debug` to see tool discovery and execution details
3. **Add routing**: Create a supervisor agent when you need multiple agents
4. **Filter tools precisely**: Use specific tool lists to minimize token usage and improve focus
5. **Test iteratively**: Use interactive mode with `reset` command between tests
6. **Handle auth gracefully**: Complete OAuth and use `continue` to resume
7. **Let agents collaborate**: Agents see previous outputs - design them to build on each other's work
8. **Template variables**: Use `{{date}}` in instructions for dynamic content

## Debug Mode

Run with `--debug` flag to see:
- Tool discovery process (which tools are found and registered)
- Tool execution details (parameters and results)
- Agent processing steps
- Error details and stack traces

Example:
```bash
python main.py --debug agents.yaml "Create a Jira ticket"
```

## Understanding Tool Execution

### How Tools Work:
1. **Discovery**: System queries Arcade for available tools based on YAML config
2. **Registration**: Each tool becomes a Semantic Kernel function with proper parameters
3. **Execution**: When agent calls a tool, the system:
   - Extracts parameters from the agent's request
   - Calls Arcade API with proper authentication
   - Returns results to the agent
   - Handles authorization if needed

### Authorization Flow Example:
```
User: "Create a Jira ticket for the login bug"
Agent: [Attempts to call Jira.CreateIssue]
System: 🔒 Authorization required. Please click here to authorize:
        https://auth.arcade-ai.com/oauth/authorize/...
User: [Completes OAuth in browser]
User: continue
Agent: [Successfully creates ticket] "Created ticket ABC-123"
```

## Capabilities & Limitations

### What It Does Well:
- **Robust OAuth handling**: Automatic auth flow with continue command
- **Smart context management**: Agents avoid duplicate API calls
- **Flexible tool permissions**: Granular control over tool access
- **Clean error handling**: Graceful degradation and clear error messages
- **Dynamic tool registration**: Tools become native Semantic Kernel functions
- **Conversation tracking**: Full history available to all agents

### Current Limitations:
- **No conversation persistence**: History lost between sessions
- **Single auth state**: One authorization at a time
- **No parallel agent execution**: Agents run sequentially
- **Basic logging**: Use debug mode for detailed output
- **No streaming responses**: Agents return complete responses

### Best For:
- Rapid prototyping of multi-agent workflows
- Testing agent collaboration patterns
- Building tool-enabled AI assistants
- Learning agent system design

For production use, consider adding persistence, advanced logging, and monitoring. But for experimentation and development, this system provides a powerful yet simple foundation.


# Main (main.py) Code Breakdown
 
## Overview

`main.py` implements a **YAML-driven multi-agent system** using Microsoft's Semantic Kernel framework. It creates AI agents from YAML configuration files and optionally integrates with Arcade for tool functionality. The system supports multiple agents working together with a supervisor agent routing requests between them.

## Core Architecture

### 1. **YAMLAgentSystem Class**

This is the main orchestrator that:
- Loads agent configurations from YAML files
- Creates Semantic Kernel agents with OpenAI integration
- Manages conversation flow between agents
- Handles Arcade tool execution and authorization

### 2. **Key Components**

```python
class YAMLAgentSystem:
    def __init__(self, config_path: str = "agents.yaml", debug: bool = False):
        self.config = {}          # YAML configuration
        self.agents = {}          # Created agents
        self.arcade = None        # Arcade client
        self.conversation = []    # Conversation history
        self.auth_required = None # Track auth requirements
```

## How It Works

### Step 1: Initialization

When the system starts, it:

1. **Loads YAML Configuration** (lines 49-52):
   ```python
   with open(self.config_path, 'r') as f:
       self.config = yaml.safe_load(f)
   ```

2. **Initializes Arcade** (lines 54-60):
   - Only if Arcade is installed AND agents have tools defined
   - Uses `ARCADE_API_KEY` from environment
   - Creates single Arcade client instance for all agents

3. **Creates Agents** (lines 64-70):
   - Iterates through each agent in YAML config
   - Creates Semantic Kernel agent with tools if specified

### Step 2: Agent Creation Process

The `_create_agent` method (lines 72-104) does the following:

1. **Creates a Kernel instance** - The core Semantic Kernel component
2. **Adds OpenAI service** - For LLM capabilities
3. **Creates tools plugin** if tools are specified in YAML
4. **Processes instructions** - Including template variables like `{{date}}`
5. **Returns ChatCompletionAgent** with all configurations

## Arcade Integration Deep Dive

### How Arcade Tools are Discovered and Registered

The magic happens in `_create_tools_plugin` (lines 106-259). Here's the detailed flow:

#### 1. **Tool Discovery** (lines 135-179):

```python
all_tools = list(self.arcade.tools.list())  # Get all available Arcade tools
```

For each tool, the system:
- Extracts the fully qualified name (e.g., `Jira.CreateIssue@0.2.0`)
- Checks if it's allowed based on YAML configuration
- Creates individual Semantic Kernel functions for allowed tools

#### 2. **Tool Filtering Logic**:

The YAML can specify tools in two ways:

**Simple Toolkit**:
```yaml
tools:
  - Jira    # Allow all Jira tools
```

**Specific Tools**:
```yaml
tools:
  - toolkit: Jira
    tools:
      - CreateIssue
      - GetIssue
```

The filtering logic (lines 149-163) checks:
- If specific tools are listed, only include those exact tools
- Otherwise, include all tools from allowed toolkits

#### 3. **Dynamic Function Creation** (lines 181-256):

For each allowed tool, the system creates a Semantic Kernel function dynamically:

```python
@kernel_function(
    name=method_name,
    description=description
)
async def tool_function(**kwargs) -> str:
    # Execute Arcade tool
```

Key aspects:
- **Parameter extraction** from tool schema (lines 187-194)
- **Closure creation** to capture tool info (line 197)
- **Error handling** for authorization (lines 230-250)

### How Tool Execution Works

When an agent calls a tool:

1. **Parameters are extracted** (lines 204-207):
   ```python
   params = kwargs
   if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], dict):
       params = kwargs['kwargs']
   ```

2. **Arcade executes the tool** (lines 215-219):
   ```python
   result = self.arcade.tools.execute(
       tool_name=tool_full_name,
       input=params,
       user_id=os.getenv('ARCADE_USER_ID', 'default')
   )
   ```

3. **Result extraction** (lines 225-228):
   - Handles nested output structures
   - Converts to string for agent consumption

### Authorization Handling

A critical feature is OAuth authorization handling (lines 230-250):

1. **Catches PermissionDeniedError**
2. **Calls `arcade.tools.authorize()`** to get auth URL
3. **Sets system flag** `system.auth_required = auth.url`
4. **Returns special marker** `🔒 AUTHORIZATION_REQUIRED: {url}`

The system then:
- Breaks the agent execution loop
- Shows auth URL to user
- Allows user to type `continue` after authorizing

## Agent Routing and Execution

### Supervisor Pattern

The system uses a supervisor agent to route requests:

1. **User makes request** → Added to conversation
2. **Supervisor agent decides** which agent should handle it (lines 314-323)
3. **Selected agent executes** with full conversation context
4. **Response added to conversation**
5. **Loop continues** until supervisor returns "COMPLETE"

### Conversation Context Management

The system maintains conversation history with special formatting (lines 332-346):

```
User: [user input]

[Previous Agent Output]
Agent1: [response]
[End of Previous Agent Output]

[Previous Agent Output]
Agent2: [response]
[End of Previous Agent Output]
```

This helps agents avoid duplicate API calls by seeing what data was already retrieved.

## Execution Modes

### 1. **Single Request Mode**:
```bash
python main.py config.yaml "Get all Jira issues assigned to me"
```

### 2. **Interactive Mode**:
```bash
python main.py config.yaml
```

Features:
- `exit` - quit
- `reset` - clear conversation
- `continue` - retry after authorization

## Debug Mode

With `--debug` flag, you see:
- Tool discovery process
- Tool call parameters
- Agent processing steps
- Error details

## Error Handling

The system handles:
- Missing Arcade installation (graceful degradation)
- Missing API keys (warning messages)
- Tool execution errors (returned to agent)
- Authorization requirements (special flow)
- Agent errors (caught and reported)

## Key Design Decisions

1. **Single Arcade Client**: Shared across all agents for efficiency
2. **Lazy Tool Loading**: Tools discovered only when agents are created
3. **Dynamic Function Generation**: Tools become native Semantic Kernel functions
4. **Authorization State Tracking**: System-level flag for auth requirements
5. **Conversation Persistence**: Full history passed to each agent

This architecture allows for flexible, YAML-configured multi-agent systems with powerful tool capabilities through Arcade, while maintaining clean separation of concerns and robust error handling.