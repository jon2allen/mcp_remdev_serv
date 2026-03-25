import asyncio
import os
import sys
from mcp_remdev_serv import (
    run_command, file_write, get_current_dir, remote_system_info, 
    list_remote_files, list_dir, find_by_name, grep_search, 
    replace_file_content, multi_replace_file_content, view_file,
    search_replace, git_grep, project_todo
)

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
    for line in files.strip().split("\n")[:10]: # limit output
        print(f"      {line}")

    # 6. Test list_dir (with time sorting)
    print("\n6. Testing list_dir (sorted by time):")
    res_list = await list_dir(".", sort_by="time")
    print(f"   Contents (newest first):\n      {res_list.strip().replace('\n', '\n      ')}")

    # 7. Test find_by_name (with time sorting)
    print("\n7. Testing find_by_name (sorted by time, looking for *.py):")
    res_find = await find_by_name("*.py", sort_by="time")
    print(f"   Found:\n      {res_find.strip().replace('\n', '\n      ')}")

    # 8. Test grep_search
    print("\n8. Testing grep_search (looking for 'Timestamp'):")
    res_grep = await grep_search("Timestamp", ".")
    print(f"   Matches:\n      {res_grep.strip().replace('\n', '\n      ')}")

    # 9. Test replace_file_content (replace_all)
    print("\n9. Testing replace_file_content (with replace_all=True):")
    # First, let's add some repetitive content
    await file_write("repeat.txt", "red blue red green red yellow\n")
    res_replace_all = await replace_file_content("repeat.txt", "red", "purple", replace_all=True)
    print(f"   Result: {res_replace_all}")
    content_repeat = await view_file("repeat.txt")
    print(f"   File Content: {content_repeat.strip()}")

    # 10. Test replace_file_content (original single replacement)
    print("\n10. Testing replace_file_content (single replacement):")
    res_replace = await replace_file_content("mcp_test.txt", "2026-02-05", "2026-03-24")
    print(f"   Result: {res_replace}")

    # 10. Test multi_replace_file_content
    print("\n10. Testing multi_replace_file_content:")
    mult_res = await multi_replace_file_content("mcp_test.txt", [
        {"TargetContent": "Timestamp", "ReplacementContent": "Last Updated"},
        {"TargetContent": "Antigravity Power Tool Server", "ReplacementContent": "Enhanced Remote Server"}
    ])
    print(f"   Result: {mult_res}")

    # 11. Test search_replace (Vibe style)
    print("\n11. Testing Vibe-style search_replace:")
    vibe_block = """<<<<<<< SEARCH
Enhanced Remote Server
=======
Vibe-Integrated Remote Dev Server
>>>>>>> REPLACE"""
    res_vibe = await search_replace("mcp_test.txt", vibe_block)
    print(f"   Result: {res_vibe}")

    # 12. Test git_grep
    print("\n12. Testing git_grep (respects .gitignore):")
    res_gitgrep = await git_grep("Enhanced", ".")
    print(f"   Git Grep matches for 'Enhanced':\n      {res_gitgrep.strip()}")

    # 13. Test project_todo
    print("\n13. Testing project_todo (Structured TODO):")
    # Clear / Init
    await project_todo("add", content="Complete the 64-bit PCLU port", priority="high")
    await project_todo("add", content="Fix alignment in _chan.c", priority="medium")
    res_todo = await project_todo("read")
    print(f"   Current TODO.json:\n      {res_todo.strip().replace('\n', '\n      ')}")

    # Final verify
    print("\nFinal File Content (mcp_test.txt):")
    final_content = await view_file("mcp_test.txt")
    print(f"      {final_content.strip().replace('\n', '\n      ')}")

    print("\n--- Test Complete ---")

if __name__ == "__main__":
    if not os.environ.get("REMOTE_HOST"):
        print("Error: REMOTE_HOST environment variable not set. Please run via run_test.sh")
        sys.exit(1)
        
    asyncio.run(main())
