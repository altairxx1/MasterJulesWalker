import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer, util

class SemanticIndexer:
    def __init__(self, project_root, model_name='all-MiniLM-L6-v2', index_base_dir_name='.masterjuleswalker_cache'):
        """
        Initializes the SemanticIndexer.

        Args:
            project_root (str): The root directory of the project to be indexed.
            model_name (str, optional): The name of the sentence-transformer model to use.
                                        Defaults to 'all-MiniLM-L6-v2'.
            index_base_dir_name (str, optional): The name of the base directory for cache/index files.
                                               Defaults to '.masterjuleswalker_cache'.
        """
        self.project_root = os.path.abspath(project_root)
        self.index_dir = os.path.join(self.project_root, index_base_dir_name, 'semantic_index')
        self.embeddings_path = os.path.join(self.index_dir, 'embeddings.npy')
        self.metadata_path = os.path.join(self.index_dir, 'metadata.json')

        self.model = None
        self.initialization_error = None
        try:
            self.model = SentenceTransformer(model_name)
        except Exception as e:
            self.initialization_error = f"Error loading SentenceTransformer model '{model_name}': {e}. Semantic search may not be available."
            # Optionally, print this error to stderr or log it
            print(f"SemanticIndexer Init Error: {self.initialization_error}")


        self.corpus_embeddings = None
        self.corpus_metadata = None

    def _chunk_file_content(self, relative_filepath, file_content_string):
        """
        Splits file content into manageable chunks (paragraphs or logical blocks).

        Args:
            relative_filepath (str): The path of the file relative to the project root.
            file_content_string (str): The entire content of the file as a string.

        Returns:
            list: A list of chunk dictionaries, where each dictionary is:
                  {'text': str, 'file_path': str, 'start_line': int, 'end_line': int}
        """
        chunks = []
        if not file_content_string:
            return chunks

        lines = file_content_string.splitlines()

        current_chunk_lines = []
        current_chunk_start_line = 0
        min_words_for_chunk = 5

        for i, line_text in enumerate(lines):
            line_number = i + 1 # 1-indexed

            if line_text.strip(): # Non-empty line
                if not current_chunk_lines: # Start of a new chunk
                    current_chunk_start_line = line_number
                current_chunk_lines.append(line_text)
            else: # Empty line signifies a paragraph break
                if current_chunk_lines:
                    chunk_text = "\n".join(current_chunk_lines)
                    # Filter out very short chunks
                    if len(chunk_text.split()) >= min_words_for_chunk or len(lines) == len(current_chunk_lines):
                        chunks.append({
                            'text': chunk_text,
                            'file_path': relative_filepath,
                            'start_line': current_chunk_start_line,
                            'end_line': line_number -1 # Previous line was the end of this chunk
                        })
                    current_chunk_lines = []
                    current_chunk_start_line = 0

        # Add the last processed chunk if any
        if current_chunk_lines:
            chunk_text = "\n".join(current_chunk_lines)
            if len(chunk_text.split()) >= min_words_for_chunk or len(lines) == len(current_chunk_lines) :
                chunks.append({
                    'text': chunk_text,
                    'file_path': relative_filepath,
                    'start_line': current_chunk_start_line,
                    'end_line': len(lines)
                })

        return chunks

    def build_index(self, files_relative_to_project_root):
        """
        Builds the semantic index from a list of files.

        Args:
            files_relative_to_project_root (list): A list of file paths relative to the project root.
        """
        if self.model is None:
            error_msg = "Semantic model not loaded. Cannot build index."
            if self.initialization_error:
                error_msg += f" Reason: {self.initialization_error}"
            print(error_msg)
            return

        all_chunks_metadata = []
        all_chunk_texts = []

        relevant_extensions = ('.py', '.md', '.txt', '.rst', '.java', '.js', '.ts', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.php', '.rb', '.swift', '.kt', '.html', '.css', '.json', '.yaml', '.yml', '.xml', '.sh') # Extensible list

        for relative_filepath in files_relative_to_project_root:
            if not relative_filepath.lower().endswith(relevant_extensions):
                # print(f"Skipping non-text/code file: {relative_filepath}") # Optional: for debugging
                continue

            abs_filepath = os.path.join(self.project_root, relative_filepath)

            try:
                with open(abs_filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except IOError as e:
                print(f"Error reading file {relative_filepath}: {e}")
                continue

            if content:
                chunks = self._chunk_file_content(relative_filepath, content)
                for chunk in chunks:
                    all_chunk_texts.append(chunk['text'])
                    all_chunks_metadata.append(chunk) # chunk already has file_path, start_line, end_line

        if all_chunk_texts:
            try:
                print(f"Encoding {len(all_chunk_texts)} text chunks for indexing...")
                self.corpus_embeddings = self.model.encode(all_chunk_texts, show_progress_bar=False) # Set to True for UI later
                self.corpus_metadata = all_chunks_metadata

                os.makedirs(self.index_dir, exist_ok=True)

                np.save(self.embeddings_path, self.corpus_embeddings)
                with open(self.metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(self.corpus_metadata, f, indent=2)

                print(f"Index built successfully with {len(all_chunk_texts)} chunks. Saved to {self.index_dir}")
            except Exception as e:
                print(f"Error during index building or saving: {e}")
                # Potentially clear partial data
                self.corpus_embeddings = None
                self.corpus_metadata = None
        else:
            print("No suitable content found across provided files to build index.")
            # Optionally clear existing index files if no new content is found
            if os.path.exists(self.embeddings_path): os.remove(self.embeddings_path)
            if os.path.exists(self.metadata_path): os.remove(self.metadata_path)
            self.corpus_embeddings = None
            self.corpus_metadata = None


    def load_index(self):
        """
        Loads the index from disk.

        Returns:
            bool: True if index was loaded successfully, False otherwise.
        """
        if self.model is None:
            error_msg = "Semantic model not loaded. Cannot load index."
            if self.initialization_error: # Provide more specific reason if model loading failed
                error_msg += f" Reason: {self.initialization_error}"
            print(error_msg)
            return False

        if os.path.exists(self.embeddings_path) and os.path.exists(self.metadata_path):
            try:
                self.corpus_embeddings = np.load(self.embeddings_path)
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self.corpus_metadata = json.load(f)
                print(f"Index loaded successfully from {self.index_dir}. Found {len(self.corpus_metadata)} chunks.")
                return True
            except Exception as e:
                print(f"Error loading index from {self.index_dir}: {e}")
                self.corpus_embeddings = None
                self.corpus_metadata = None
                return False
        else:
            print(f"Index files not found in {self.index_dir}. Please build the index first.")
            return False

    def get_loaded_data(self):
        """
        Returns the loaded corpus embeddings and metadata.

        Returns:
            tuple: (numpy.ndarray, list) or (None, None) if not loaded.
        """
        return self.corpus_embeddings, self.corpus_metadata

    def search(self, query_text: str, top_n: int = 10):
        """
        Performs a semantic search for the query_text against the loaded index.

        Args:
            query_text (str): The text to search for.
            top_n (int, optional): The number of top results to return. Defaults to 10.

        Returns:
            dict: A dictionary containing either "results" (a list of search hits)
                  or "error" (a string describing an issue).
                  Each search hit is a dictionary:
                  {
                      'file_path': str,
                      'start_line': int,
                      'end_line': int,
                      'text': str, # The text of the chunk
                      'score': float # Similarity score
                  }
        """
        if self.initialization_error or self.model is None:
            return {"error": f"Cannot search, model not initialized: {self.initialization_error or 'Unknown reason'}"}

        if self.corpus_embeddings is None or self.corpus_metadata is None:
            print("Search: Index not currently in memory. Attempting to load...")
            if not self.load_index() or self.corpus_embeddings is None or self.corpus_metadata is None:
                return {"error": "Index not loaded or empty. Please build the index first."}

        if not query_text or not query_text.strip():
            return {"error": "Search query cannot be empty."}

        try:
            query_embedding = self.model.encode(query_text)

            # Ensure corpus_embeddings is a 2D numpy array
            if self.corpus_embeddings is None or len(self.corpus_embeddings.shape) != 2:
                 return {"error": "Corpus embeddings are not correctly loaded or are not 2D."}


            hits = util.semantic_search(query_embedding, self.corpus_embeddings, top_k=top_n)

            search_results = []
            if hits and hits[0]: # hits is a list of lists, one per query
                for hit in hits[0]:
                    corpus_id = hit['corpus_id']
                    score = hit['score']
                    if 0 <= corpus_id < len(self.corpus_metadata):
                        metadata_item = self.corpus_metadata[corpus_id]
                        search_results.append({
                            'file_path': metadata_item['file_path'],
                            'start_line': metadata_item['start_line'],
                            'end_line': metadata_item['end_line'],
                            'text': metadata_item['text'],
                            'score': score
                        })
                    else:
                        print(f"Warning: corpus_id {corpus_id} out of bounds for metadata (len: {len(self.corpus_metadata)}). Skipping hit.")

            return {"results": search_results}

        except Exception as e:
            # Log the exception details for debugging if necessary
            # logger.error(f"Error during semantic search: {e}", exc_info=True)
            return {"error": f"An error occurred during search: {e}"}


if __name__ == '__main__':
    print("SemanticIndexer test script started.")

    # Setup a dummy project structure for testing
    test_project_root = "_test_semantic_indexer_project_main"
    os.makedirs(test_project_root, exist_ok=True)

    # Create some dummy files
    dummy_files_data = {
        "file1.py": "def hello_world():\n    print('Hello Python world!')\n\n# This is a comment\n\nclass MyClass:\n    pass",
        "notes.md": "# Project Notes\n\nThis is a note about the project.\n\n## Subsection\nMore details here.",
        "config.txt": "key=value\nanother_key=another_value",
        "ignored.log": "This file should be ignored by extension.",
        "empty.py": ""
    }

    files_to_index = []
    for filename, content in dummy_files_data.items():
        filepath = os.path.join(test_project_root, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        if not filename.endswith(".log"): # Don't try to index log files based on current build_index logic
            files_to_index.append(filename)

    print(f"\n1. Initializing SemanticIndexer for project: {test_project_root}")
    # Use a smaller, faster model for testing if available and if the default is slow,
    # but for now, stick to the default to ensure it works.
    # model_name = 'paraphrase-MiniLM-L3-v2' # Example of a smaller model
    indexer = SemanticIndexer(project_root=test_project_root)

    if indexer.initialization_error:
        print(f"(!) Indexer initialization failed: {indexer.initialization_error}")
        print("   Skipping further tests that require the model.")
    else:
        print("   Indexer initialized successfully.")

        print("\n2. Building index...")
        indexer.build_index(files_to_index) # Pass relative paths

        # Verify index files were created (basic check)
        if os.path.exists(indexer.embeddings_path) and os.path.exists(indexer.metadata_path):
            print(f"   Index files seem to be created at: {indexer.index_dir}")
        else:
            print(f"   (!) Index files NOT found at: {indexer.index_dir}")


        print("\n3. Loading index...")
        load_status = indexer.load_index()
        if load_status:
            print("   Index loaded successfully.")
            embeddings, metadata = indexer.get_loaded_data()
            if embeddings is not None and metadata is not None:
                print(f"   Loaded {len(metadata)} chunks with embedding shape {embeddings.shape}")

                # Optional: Print some metadata for verification
                # print("\n   Sample metadata from loaded index (first 2 chunks):")
                # for i, item in enumerate(metadata[:2]):
                #     print(f"     Chunk {i+1}: File='{item['file_path']}', Lines {item['start_line']}-{item['end_line']}, Text='{item['text'][:30]}...'")
            else:
                print("   (!) Loaded data is None despite load_index returning True.")
        else:
            print("   (!) Index loading failed.")

        # Test _chunk_file_content directly for one file to see output
        print("\n4. Testing _chunk_file_content directly on file1.py...")
        file1_content = dummy_files_data["file1.py"]
        chunks_file1 = indexer._chunk_file_content("file1.py", file1_content)
        print(f"   Found {len(chunks_file1)} chunks in file1.py:")
        for i, chunk in enumerate(chunks_file1):
            print(f"     Chunk {i+1}: Lines {chunk['start_line']}-{chunk['end_line']}, Text: '{chunk['text'][:50].replace('\n', ' ')}...'")

        print("\n5. Performing searches...")
        queries = [
            "python hello world function",
            "project documentation",
            "class definition",
            "how to configure application", # Should match config.txt
            "non_existent_topic_for_sure"
        ]

        for query in queries:
            print(f"\n   Searching for: '{query}'")
            search_response = indexer.search(query_text=query, top_n=2)
            if "error" in search_response:
                print(f"     Error: {search_response['error']}")
            elif search_response["results"]:
                print("     Results:")
                for hit in search_response["results"]:
                    print(f"       - File: {hit['file_path']} (Lines {hit['start_line']}-{hit['end_line']})")
                    print(f"         Score: {hit['score']:.4f}")
                    print(f"         Text: '{hit['text'][:80].replace('\n', ' ')}...'")
            else:
                print("     No results found.")


    # Clean up the dummy project directory
    print("\n6. Cleaning up dummy project directory...")
    try:
        import shutil
        shutil.rmtree(test_project_root)
        print(f"   Successfully removed: {test_project_root}")
    except Exception as e:
        print(f"   (!) Error cleaning up dummy project directory: {e}")

    print("\nSemanticIndexer test script finished.")
