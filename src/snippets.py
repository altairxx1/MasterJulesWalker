import json
import os
import uuid

# Snippet Structure:
# {
#     "id": "unique_string_id", # Using UUID for more robust IDs
#     "name": "Descriptive Name",
#     "content": "The actual code snippet",
#     "language": "python", # Or "javascript", "bash", etc.
#     "category": "General", # User-defined category
#     "tags": ["tag1", "tag2"] # List of strings
# }

class SnippetManager:
    def __init__(self, filepath="snippets.json"):
        self.filepath = filepath
        self.snippets = []
        # _next_id is not needed if using UUIDs
        self._load_snippets()

    def _load_snippets(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r') as f:
                    self.snippets = json.load(f)
                # Validate basic structure (optional, but good for robustness)
                for snippet in self.snippets:
                    if not all(k in snippet for k in ['id', 'name', 'content']):
                        # Or raise a custom error
                        print(f"Warning: Loaded snippet missing essential keys: {snippet.get('id')}")
                        # Potentially remove invalid snippets or handle differently
            else:
                self.snippets = []
        except FileNotFoundError:
            self.snippets = [] # File doesn't exist, start fresh
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {self.filepath}. Starting with an empty snippet list.")
            self.snippets = [] # Corrupted file, start fresh
        # No explicit _next_id update needed with UUIDs

    def _save_snippets(self):
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.snippets, f, indent=2)
        except IOError as e:
            print(f"Error: Could not save snippets to {self.filepath}: {e}")
            # Potentially raise this error or handle more gracefully in UI

    def add_snippet(self, name, content, language="python", category="General", tags=None):
        if not name or not name.strip():
            print("Error: Snippet name cannot be empty.")
            return None
        if not content or not content.strip():
            print("Error: Snippet content cannot be empty.")
            return None

        if tags is None:
            tags = []

        new_snippet = {
            "id": str(uuid.uuid4()), # Generate a unique string ID
            "name": name.strip(),
            "content": content,
            "language": language.lower().strip(),
            "category": category.strip() if category else "General",
            "tags": [str(tag).strip() for tag in tags if str(tag).strip()] # Ensure tags are strings and stripped
        }

        self.snippets.append(new_snippet)
        self._save_snippets()
        return new_snippet

    def list_snippets(self):
        # Return a copy to prevent external modification of the internal list
        return list(self.snippets)

    def get_snippet_by_id(self, snippet_id):
        for snippet in self.snippets:
            if snippet['id'] == snippet_id:
                return snippet
        return None

    def delete_snippet(self, snippet_id):
        original_length = len(self.snippets)
        self.snippets = [s for s in self.snippets if s['id'] != snippet_id]
        if len(self.snippets) < original_length:
            self._save_snippets()
            return True
        return False

    def update_snippet(self, snippet_id, name=None, content=None, language=None, category=None, tags=None):
        snippet = self.get_snippet_by_id(snippet_id)
        if not snippet:
            return None

        updated = False
        if name is not None and name.strip() and snippet['name'] != name.strip():
            snippet['name'] = name.strip()
            updated = True
        if content is not None and content.strip() and snippet['content'] != content: # Content can be just whitespace
            snippet['content'] = content
            updated = True
        if language is not None and language.lower().strip() and snippet['language'] != language.lower().strip():
            snippet['language'] = language.lower().strip()
            updated = True
        if category is not None and snippet['category'] != category.strip():
            snippet['category'] = category.strip() if category.strip() else "General"
            updated = True
        if tags is not None: # Allow clearing tags with []
            new_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
            if snippet['tags'] != new_tags:
                snippet['tags'] = new_tags
                updated = True

        if updated:
            self._save_snippets()
        return snippet

# Example Usage (for testing this file directly):
if __name__ == "__main__":
    sm = SnippetManager(filepath="test_snippets.json")

    # Clean up old test file if exists
    if os.path.exists("test_snippets.json"):
        os.remove("test_snippets.json")

    print("Initial snippets:", sm.list_snippets())

    s1 = sm.add_snippet("Python Hello", "print('Hello, Python!')", "python", "Greetings", ["hello", "python"])
    s2 = sm.add_snippet("JS Alert", "alert('Hello, JS!');", "javascript", "Web", ["hello", "javascript", "alert"])

    print("\nSnippets after adding:")
    for s in sm.list_snippets():
        print(s)

    if s1:
        print(f"\nGetting snippet by ID ({s1['id']}):")
        print(sm.get_snippet_by_id(s1['id']))

    if s2:
        print(f"\nUpdating snippet {s2['id']}")
        updated_s2 = sm.update_snippet(s2['id'], name="JS Hello Alert", category="JavaScript Examples", tags=["js", "alert", "greeting"])
        print(updated_s2)

    print("\nSnippets after update:")
    for s in sm.list_snippets():
        print(s)

    if s1:
        print(f"\nDeleting snippet {s1['id']}...")
        deleted = sm.delete_snippet(s1['id'])
        print(f"Deleted: {deleted}")

    print("\nSnippets after deleting:")
    for s in sm.list_snippets():
        print(s)

    # Test loading (manager2 should load from test_snippets.json created by sm)
    print("\nLoading into new manager...")
    sm2 = SnippetManager(filepath="test_snippets.json")
    print("Snippets in sm2:")
    for s in sm2.list_snippets():
        print(s)

    if os.path.exists("test_snippets.json"):
        os.remove("test_snippets.json")
        print("\nCleaned up test_snippets.json")
