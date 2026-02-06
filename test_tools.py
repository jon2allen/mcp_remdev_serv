import asyncio
import os
import sys
from mcp_remdev_serv import run_command, file_write, get_current_dir, remote_system_info, list_remote_files

async def main():
    print("--- Starting MCP Remote Dev Tool Test ---")
    
    # 1. Get system info to verify connection/config
    print("\n1. Verifying Remote System Info:")
    info = await remote_system_info()
    print(f"   Target: {info['host']}:{info['port']} ({info['os_type']})")
    print(f"   Remote Dir: {info['current_dir']}")

    # 2. Check current directory
    print("\n2. Getting Current Directory:")
    curr_dir = await get_current_dir()
    print(f"   Current dir is: {curr_dir}")

    # 3. Create a file called mcp_test.txt
    print("\n3. Creating 'mcp_test.txt' on remote:")
    file_content = "This is a test file created by the MCP Remote Dev Server.\nTimestamp: 2026-02-05\n"
    res_write = await file_write("mcp_test.txt", file_content)
    print(f"   Result: {res_write}")

    # 4. List the directory (ls -l)
    print("\n4. Listing directory (ls -l):")
    res_ls = await run_command("ls -l")
    
    if res_ls["is_error"]:
        print("   Error listing directory!")
    
    for msg in res_ls["content"]:
        if msg["name"] == "STDOUT":
            print("   STDOUT Output:")
            # Indent output for readability
            for line in msg["text"].strip().split("\n"):
                print(f"      {line}")
        elif msg["name"] == "STDERR" and msg["text"]:
            print(f"   STDERR: {msg['text']}")
        elif msg["name"] == "EXIT_CODE":
            print(f"   Exit Code: {msg['text']}")

    # 5. List remote files for discovery
    print("\n5. Discovery - Listing remote files (find):")
    files = await list_remote_files()
    print("   Remote Files Found:")
    for line in files.strip().split("\n"):
        print(f"      {line}")

    print("\n--- Test Complete ---")

if __name__ == "__main__":
    if not os.environ.get("REMOTE_HOST"):
        print("Error: REMOTE_HOST environment variable not set. Please run via run_test.sh")
        sys.exit(1)
        
    asyncio.run(main())
