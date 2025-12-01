import os
import glob

def print_tree(startpath, depth=2):
    print(f"# --- Tree for {os.path.basename(os.path.abspath(startpath))} --- #")
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        if level > depth: continue
        
        indent = ' ' * 4 * level
        print(f"{indent}{os.path.basename(root)}/")
        
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if f.endswith('.pyc') or f.startswith('.'): continue
            print(f"{subindent}{f}")
            
        # Remove hidden/venv dirs to keep it clean
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'node_modules', '__pycache__')]

def get_latest_progress(file_path: str) -> str:
    """
    Reads the curr_progress.md file and returns only the content from the last '##' header.
    This ensures that only the latest entry is included in the context.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find the index of the last '##' (markdown header for date/step)
        last_header_index = content.rfind('##')

        if last_header_index != -1:
            # Slice the content from the last header index to the end
            latest_progress = content[last_header_index:].strip()
        else:
            # If no '##' is found, return the full content
            latest_progress = content.strip()
            
        return latest_progress

    except FileNotFoundError:
        return f"Error: Progress file not found at {file_path}"
    except Exception as e:
        return f"An error occurred while processing the progress file: {e}"

def print_schema_status():
    print(f"### [Schema Status] ###")
    schema_dir = "api/app/schemas"
    if not os.path.exists(schema_dir):
        print("No schema directory found.")
        return

    print(f"Listing of '{os.path.abspath(schema_dir)}':")
    files = glob.glob(os.path.join(schema_dir, "*.py"))
    for file_path in sorted(files):
        filename = os.path.basename(file_path)
        if filename == "__init__.py": continue
        
        print(f"--- File: {filename} ---")
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Print first 15 lines as summary
            print("".join(lines[:15]))
            print("...")

if __name__ == "__main__":
    # 1. Project Tree
    print("### [Project Tree] ###")
    target_dirs = ["api/app", "frontend/src", "dashboard", "docs", "scripts"]
    for d in target_dirs:
        if os.path.exists(d):
            print_tree(d, depth=1)
    
    # 2. Latest Progress
    print(f"### [Current Progress] (Latest Entry) ###\n{get_latest_progress('docs/curr_progress.md')}")
    
    # 3. Schema Status
    print_schema_status()