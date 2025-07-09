import os
from mistralai import Mistral
from typing import List, Dict
import json
from datetime import datetime
import requests
from pathlib import Path
import re
import math

def file_operation(operation: str, path: str, content: str = None) -> str:
    """
    Perform file operations (read, write, list) in a safe directory.
    Operations are restricted to a predefined safe directory to prevent unauthorized access.
    """
    SAFE_BASE_DIR = Path.home() / "devstral_sandbox"
    SAFE_BASE_DIR.mkdir(exist_ok=True)
    
    try:
        target_path = (SAFE_BASE_DIR / path).resolve()
        if not str(target_path).startswith(str(SAFE_BASE_DIR)):
            return "Error: Path is outside the allowed directory."
    except Exception as e:
        return f"Error: Invalid path - {str(e)}"
    
    try:
        if operation == "read":
            if not target_path.is_file():
                return f"Error: {path} is not a file or does not exist."
            with open(target_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        elif operation == "write":
            if content is None:
                return "Error: Content is required for write operation."
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        
        elif operation == "list":
            if not target_path.is_dir():
                return f"Error: {path} is not a directory or does not exist."
            files = [p.name for p in target_path.iterdir()]
            return "\n".join(files) if files else "Directory is empty."
        
        else:
            return f"Error: Unsupported operation '{operation}'. Use 'read', 'write', or 'list'."
    
    except PermissionError:
        return f"Error: Permission denied for {path}."
    except Exception as e:
        return f"Error during file operation: {str(e)}"

# System prompt
def get_system_prompt() -> str:
    return """You are Devstral, a helpful AI assistant created by Mistral. You can answer questions, perform web searches, execute Python code, perform calculations, and manage files in a safe directory. Provide clear, accurate, and concise responses.
For inline function calls, use the format [[calculate_math:expression]] for calculations (e.g., [[calculate_math:1+1]]), [[web_search:query]] for searches, etc. Supported functions are: get_current_time, web_search, calculate_math, run_python_script, file_operation. After an inline function call, assume the result will be provided and continue your response accordingly.
If the user asks you a mathematical question, you MUST use the calculate_math function to evaluate it, you may not not use the [[calculate_math:expression]] when solving a math problem."""

# Function definitions for tool calling
def get_current_time() -> str:
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    return f"Current local time: {current_time}"

def web_search(query: str) -> str:
    try:
        # Wikipedia API endpoint for search
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 3,  # Limit to top 3 results
            "utf8": 1
        }
        headers = {"User-Agent": f"an ai has made this search, guided by a human({email}). this is not commercial/official. I released this *custom/personal project* to github(https://github.com/sir-cakes-alot/mistral-ai-example). (contact me: pleasework413@gmail.com)"}
        
        # Make the API request
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        
        # Extract search results
        search_results = data.get("query", {}).get("search", [])
        if not search_results:
            return f"No relevant Wikipedia articles found for '{query}'."
        
        # Format the results
        results = []
        for result in search_results:
            title = result.get("title", "No title")
            snippet = result.get("snippet", "No snippet")
            # Remove HTML tags from snippet
            snippet = re.sub(r"<[^>]+>", "", snippet)
            results.append(f"- {title}: {snippet}")
        
        return "\n".join(results)
    
    except requests.RequestException as e:
        return f"Error during Wikipedia search: {str(e)}. Try a different query."
    except Exception as e:
        return f"Unexpected error during Wikipedia search: {str(e)}."

# Tool schema for Mistral API
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current local time in the system's default timezone.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Perform a web search to find information relevant to the query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_math",
            "description": "Evaluate a mathematical expression and return the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "A mathematical expression to evaluate (e.g., '2 + 3 * 4'). Supports basic arithmetic (+, -, *, /, **, parentheses)."
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_python_script",
            "description": "Execute a Python script and return the output or error.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute. Must be valid Python 3.11 code. you can define a 'result' variable to return output."
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_operation",
            "description": "Perform file operations like read, write, or list in a safe directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["read", "write", "list"]},
                    "path": {"type": "string", "description": "File or directory path."},
                    "content": {"type": "string", "description": "Content to write (for write operation)."}
                },
                "required": ["operation", "path"]
            }
        }
    }
]

# Function to execute a function call based on parsed marker
def execute_function(function_name: str, args: str) -> str:
    try:
        if function_name == "get_current_time":
            return get_current_time()
        elif function_name == "web_search":
            return web_search(args)
        elif function_name == "calculate_math":
            return str(eval(args))
        elif function_name == "run_python_script":
            exec_globals = {}
            exec(args, exec_globals)
            return str(exec_globals.get('result', 'Script executed successfully.'))
        elif function_name == "file_operation":
            args_dict = json.loads(args)
            operation = args_dict["operation"]
            path = args_dict["path"]
            content = args_dict.get("content")
            return file_operation(operation, path, content)
        else:
            return f"Error: Unknown function '{function_name}'."
    except Exception as e:
        return f"Error in {function_name}: {str(e)}"

# Function to call Mistral API with streaming support and inline function calls
def get_devstral_response(messages: List[Dict], temp) -> str:
    api_key = 'get your own key!'
    if not api_key:
        return "Error: MISTRAL_API_KEY not set."
    
    client = Mistral(api_key=api_key)
    model = "devstral-small-latest"
    assistant_content = ""
    tool_calls = []
    buffer = ""  # Buffer to accumulate content for parsing markers

    try:
        # Start streaming the initial response
        stream_response = client.chat.stream(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temp if temp is not None else 0.15,
        )
        
        # Process the streamed response
        for event in stream_response:
            if hasattr(event.data, 'choices') and event.data.choices:
                if event.data.choices[0].delta.content:
                    content = event.data.choices[0].delta.content
                    buffer += content
                    print(content, end="", flush=True)  # Stream content in real-time
                    
                    # Check for complete function call markers
                    pattern = r'\[\[(\w+):([^\]]*)\]\]'
                    match = re.search(pattern, buffer)
                    if match:
                        function_name = match.group(1)
                        args = match.group(2)
                        marker = match.group(0)
                        
                        # Execute the function
                        result = execute_function(function_name, args)
                        print(f"\nTool call executed: {function_name} with args {args} -> Result: {result}")
                        
                        # Replace the marker with the result in the assistant content
                        assistant_content += buffer[:match.start()] + str(result)
                        buffer = buffer[match.end():]
                        
                        # Append the assistant's partial message
                        messages.append({
                            "role": "assistant",
                            "content": assistant_content
                        })
                        # Append the tool result without tool_call_id to avoid API mismatch
                        messages.append({
                            "role": "assistant",
                            "content": f"[{function_name} result: {result}]"
                        })
                        
                        # Start a new stream with updated context
                        assistant_content = ""
                        follow_up_stream = client.chat.stream(
                            model=model,
                            messages=messages,
                            tools=tools,
                            tool_choice="auto",
                            temperature=temp if temp is not None else 0.15,
                        )
                        
                        # Process the follow-up stream
                        buffer = ""
                        for follow_event in follow_up_stream:
                            if hasattr(follow_event.data, 'choices') and follow_event.data.choices:
                                if follow_event.data.choices[0].delta.content:
                                    content = follow_event.data.choices[0].delta.content
                                    buffer += content
                                    assistant_content += content
                                    print(content, end="", flush=True)
                                if follow_event.data.choices[0].delta.tool_calls:
                                    tool_calls.extend(follow_event.data.choices[0].delta.tool_calls)
                                if follow_event.data.choices[0].finish_reason == "tool_calls":
                                    break
                        print()  # New line after streaming
                        buffer = ""  # Reset buffer
                        
                if event.data.choices[0].delta.tool_calls:
                    tool_calls.extend(event.data.choices[0].delta.tool_calls)
                if event.data.choices[0].finish_reason == "tool_calls":
                    break
        
        # Append any remaining buffer content
        assistant_content += buffer
        print()  # New line after streaming content
        
        # Handle standard tool calls if any
        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": assistant_content if assistant_content else None,
                "tool_calls": tool_calls
            })
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name == "get_current_time":
                    result = get_current_time()
                elif function_name == "web_search":
                    result = web_search(function_args["query"])
                elif function_name == "calculate_math":
                    try:
                        result = eval(function_args["expression"], SAFE_MATH_GLOBALS, {})
                    except Exception as e:
                        result = f"Error evaluating expression '{function_args['expression']}': {str(e)}"
                elif function_name == "run_python_script":
                    try:
                        code = function_args["code"]
                        exec_globals = {}
                        exec(code, exec_globals)
                        result = exec_globals.get('result', 'Script executed successfully.')
                    except Exception as e:
                        result = f"Error executing script: {str(e)}"
                elif function_name == "file_operation":
                    try:
                        operation = function_args["operation"]
                        path = function_args["path"]
                        content = function_args.get("content")
                        result = file_operation(operation, path, content)
                    except Exception as e:
                        result = f"Error in file operation: {str(e)}"
                else:
                    result = f"Error: Unknown function '{function_name}'."
                
                print(f"Tool call executed: {function_name} with args {function_args} -> Result: {result}")
                
                messages.append({
                    "role": "tool",
                    "content": str(result),
                    "tool_call_id": tool_call.id
                })
            
            # Start a new stream for the final response
            assistant_content = ""
            follow_up_stream = client.chat.stream(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=temp if temp is not None else 0.15,
            )
            
            for event in follow_up_stream:
                if hasattr(event.data, 'choices') and event.data.choices:
                    if event.data.choices[0].delta.content:
                        content = event.data.choices[0].delta.content
                        assistant_content += content
                        print(content, end="", flush=True)
            print()
            
            return assistant_content
        
        return assistant_content
    
    except Exception as e:
        print(f"\nError: {str(e)}")
        return f"Error: {str(e)}"

def main():
    global email
    # Initialize message history
    messages: List[Dict] = []
    # Add system prompt at the start
    messages.append({"role": "system", "content": get_system_prompt()})
    temp = 0.15  # Default temperature
    email=input('what is your email(or contact point)?: ')
    
    print("Devstral AI Chat (type 'exit' to quit, 'clear' to reset history)")
    print(f"Default temperature is set to {temp}. Type 'temp' to change it.")

    while True:
        messages = messages[-10:]  # Keep the last 10 messages for context
        user_input = input("> ")
        
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        elif user_input.lower() == "clear":
            messages.clear()
            messages.append({"role": "system", "content": get_system_prompt()})
            os.system('cls' if os.name == 'nt' else 'clear')
            continue
        elif user_input.lower() == "temp":
            temp = input("Enter temperature (default is 0.15): ")
            try:
                temp = float(temp)
            except ValueError:
                print("Invalid temperature value. Using default (0.15).")
                temp = 0.15
            continue
        elif not user_input.strip():
            print("Please enter a valid question.")
            continue
        
        # Add user message to history
        messages.append({"role": "user", "content": user_input})
        
        # Get and print assistant response
        response = get_devstral_response(messages, temp)
        
        # Add assistant response to history
        messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
