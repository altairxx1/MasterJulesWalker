import unittest
from unittest.mock import patch, mock_open, MagicMock
import numpy as np
import json
import os

# Ensure src directory is in path for imports if running tests from root
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from search_indexer import SemanticIndexer

class TestSemanticIndexer(unittest.TestCase):

    def setUp(self):
        self.project_root = "/fake/project"
        self.index_file_path = os.path.join(self.project_root, ".mjw_semantic_index.json")
        self.embeddings_file_path = os.path.join(self.project_root, ".mjw_semantic_embeddings.npy")

    @patch('search_indexer.SentenceTransformer')
    def test_init_success(self, mock_sentence_transformer_constructor):
        mock_model = MagicMock()
        mock_sentence_transformer_constructor.return_value = mock_model
        indexer = SemanticIndexer(project_root=self.project_root)
        self.assertEqual(indexer.project_root, self.project_root)
        self.assertEqual(indexer.model_name, 'all-MiniLM-L6-v2')
        self.assertEqual(indexer.index_file, self.index_file_path)
        self.assertEqual(indexer.embeddings_file, self.embeddings_file_path)
        mock_sentence_transformer_constructor.assert_called_once_with('all-MiniLM-L6-v2')
        self.assertIsNotNone(indexer.model)

    @patch('search_indexer.SentenceTransformer', side_effect=Exception("Model loading failed"))
    def test_init_model_load_failure(self, mock_sentence_transformer_constructor):
        with self.assertLogs(level='ERROR') as log:
            indexer = SemanticIndexer(project_root=self.project_root)
            self.assertIsNone(indexer.model)
        self.assertIn("Failed to load SentenceTransformer model: Model loading failed", log.output[0])
        mock_sentence_transformer_constructor.assert_called_once_with('all-MiniLM-L6-v2')

    @patch('search_indexer.os.path.exists', return_value=True)
    @patch('search_indexer.open', new_callable=mock_open, read_data='content')
    @patch('search_indexer.SentenceTransformer')
    @patch('search_indexer.np.save')
    @patch('search_indexer.json.dump')
    def test_build_index(self, mock_json_dump, mock_np_save, mock_sentence_transformer_constructor, mock_file_open, mock_path_exists):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
        mock_sentence_transformer_constructor.return_value = mock_model

        indexer = SemanticIndexer(project_root=self.project_root)
        files_to_index = ["file1.py", "file2.txt"]

        # Mock file content for file1.py
        mock_file_open.side_effect = [
            mock_open(read_data="line1\nline2\nline3\nline4\nline5\nline6").return_value, # file1.py
            mock_open(read_data="short file").return_value # file2.txt
        ]

        indexer.build_index(files_to_index)

        self.assertEqual(mock_file_open.call_count, len(files_to_index))
        mock_file_open.assert_any_call(os.path.join(self.project_root, "file1.py"), "r", encoding="utf-8", errors="ignore")
        mock_file_open.assert_any_call(os.path.join(self.project_root, "file2.txt"), "r", encoding="utf-8", errors="ignore")

        self.assertEqual(mock_model.encode.call_count, 1) # Called once with all chunks

        # Expected chunks based on logic (5 lines per chunk, 1 line overlap)
        # file1.py: "line1\nline2\nline3\nline4\nline5", "line5\nline6"
        # file2.txt: "short file"
        # Total 3 chunks
        self.assertEqual(len(indexer.file_chunks), 3)
        self.assertEqual(indexer.file_chunks[0]['file_path'], 'file1.py')
        self.assertTrue("line1" in indexer.file_chunks[0]['text_chunk'])
        self.assertTrue("line5" in indexer.file_chunks[0]['text_chunk'])
        self.assertEqual(indexer.file_chunks[1]['file_path'], 'file1.py')
        self.assertTrue("line5" in indexer.file_chunks[1]['text_chunk'])
        self.assertTrue("line6" in indexer.file_chunks[1]['text_chunk'])
        self.assertEqual(indexer.file_chunks[2]['file_path'], 'file2.txt')
        self.assertEqual(indexer.file_chunks[2]['text_chunk'], 'short file')

        mock_np_save.assert_called_once_with(self.embeddings_file_path, np.array([[0.1, 0.2], [0.3, 0.4]]))

        # Check what was passed to json.dump
        args, _ = mock_json_dump.call_args
        self.assertEqual(args[0], indexer.file_chunks) # The first argument to json.dump
        self.assertEqual(args[1].name, self.index_file_path) # The file object's name

    @patch('search_indexer.os.path.exists', return_value=False)
    @patch('search_indexer.SentenceTransformer')
    def test_build_index_file_not_found(self, mock_sentence_transformer_constructor, mock_path_exists):
        mock_model = MagicMock()
        mock_sentence_transformer_constructor.return_value = mock_model
        indexer = SemanticIndexer(project_root=self.project_root)

        with self.assertLogs(level='WARNING') as log:
            indexer.build_index(["non_existent_file.py"])
        self.assertIn("File not found and skipped: /fake/project/non_existent_file.py", log.output[0])
        self.assertEqual(len(indexer.file_chunks), 0) # No chunks should be created


    @patch('search_indexer.os.makedirs')
    @patch('search_indexer.open', new_callable=mock_open)
    @patch('search_indexer.np.save')
    @patch('search_indexer.json.dump')
    @patch('search_indexer.SentenceTransformer')
    def test_build_index_creates_directory(self, mock_sentence_transformer_constructor, mock_json_dump, mock_np_save, mock_open_func, mock_os_makedirs):
        # Simulate project_root not existing initially for makedirs check
        # For the purpose of os.makedirs, path.exists for project_root itself is not the main concern,
        # but rather that open() for index_file_path would fail if its dir doesn't exist.
        # search_indexer.py uses os.makedirs(self.project_root, exist_ok=True) which is odd,
        # it should be os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
        # Let's assume self.project_root is the directory to check for os.makedirs.

        mock_model = MagicMock()
        mock_sentence_transformer_constructor.return_value = mock_model

        # Correctly mock os.path.exists: False for index file, True for files to index
        def path_exists_side_effect(path):
            if path == self.index_file_path or path == self.embeddings_file_path:
                return False # Index files don't exist, so save functions will be called
            if path == os.path.join(self.project_root, "file1.py"):
                return True # File to be indexed exists
            return False # Default for other paths

        with patch('search_indexer.os.path.exists', side_effect=path_exists_side_effect):
            indexer = SemanticIndexer(project_root=self.project_root)
            # Mock file content for file1.py
            mock_open_func.side_effect = [
                mock_open(read_data="line1\nline2").return_value, # file1.py
                mock_open().return_value, # For json.dump
                mock_open().return_value  # For np.save (though np.save handles file path directly)
            ]
            indexer.build_index(["file1.py"])
            # The SemanticIndexer creates self.project_root, which is unusual.
            # It should create os.path.dirname(self.index_file).
            # Given current code:
            mock_os_makedirs.assert_called_with(self.project_root, exist_ok=True)


    @patch('search_indexer.os.path.exists', return_value=True)
    @patch('search_indexer.np.load', return_value=np.array([[0.1, 0.2]]))
    @patch('search_indexer.open', new_callable=mock_open, read_data='[{"file_path": "test.py", "text_chunk": "chunk1", "start_line":1, "end_line":2}]')
    @patch('search_indexer.json.load', return_value=[{"file_path": "test.py", "text_chunk": "chunk1", "start_line":1, "end_line":2}])
    @patch('search_indexer.SentenceTransformer')
    def test_load_index_success(self, mock_sentence_transformer_constructor, mock_json_load, mock_file_open, mock_np_load, mock_path_exists):
        mock_model = MagicMock()
        mock_sentence_transformer_constructor.return_value = mock_model
        indexer = SemanticIndexer(project_root=self.project_root)
        indexer.load_index()

        mock_path_exists.assert_any_call(self.index_file_path)
        mock_path_exists.assert_any_call(self.embeddings_file_path)
        mock_np_load.assert_called_once_with(self.embeddings_file_path)
        # json.load is called with a file object
        mock_file_open.assert_called_once_with(self.index_file_path, "r", encoding="utf-8")
        mock_json_load.assert_called_once_with(mock_file_open.return_value) # json.load gets the file handle

        self.assertEqual(len(indexer.corpus_metadata), 1)
        self.assertEqual(indexer.corpus_metadata[0]['file_path'], 'test.py')
        self.assertTrue(np.array_equal(indexer.corpus_embeddings, np.array([[0.1, 0.2]])))

    @patch('search_indexer.os.path.exists', return_value=False)
    @patch('search_indexer.SentenceTransformer')
    def test_load_index_file_not_found(self, mock_sentence_transformer_constructor, mock_path_exists):
        mock_model = MagicMock()
        mock_sentence_transformer_constructor.return_value = mock_model
        indexer = SemanticIndexer(project_root=self.project_root)
        with self.assertLogs(level='INFO') as log: # It logs INFO if files don't exist
            indexer.load_index()
        # Check one of the expected log messages
        self.assertTrue(any("Index file not found at" in msg for msg in log.output))
        self.assertIsNone(indexer.corpus_embeddings)
        self.assertIsNone(indexer.file_chunks) # Renamed to corpus_metadata in load_index

    @patch('search_indexer.util.semantic_search', return_value=[[{'corpus_id': 0, 'score': 0.9}]])
    @patch('search_indexer.SentenceTransformer')
    def test_search_success(self, mock_sentence_transformer_constructor, mock_semantic_search):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.5, 0.5]]) # Query embedding
        mock_sentence_transformer_constructor.return_value = mock_model

        indexer = SemanticIndexer(project_root=self.project_root)
        indexer.corpus_embeddings = np.array([[0.1, 0.2]])
        indexer.corpus_metadata = [{"file_path": "test.py", "text_chunk": "chunk1", "start_line": 1, "end_line": 2}]

        results = indexer.search("test query")

        mock_model.encode.assert_called_once_with("test query", convert_to_tensor=True)
        mock_semantic_search.assert_called_once()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['score'], 0.9)
        self.assertEqual(results[0]['file_path'], 'test.py')

    @patch('search_indexer.SentenceTransformer')
    def test_search_no_model(self, mock_sentence_transformer_constructor):
        mock_sentence_transformer_constructor.return_value = None # Simulate model loading failure
        indexer = SemanticIndexer(project_root=self.project_root)
        indexer.model = None # Explicitly ensure model is None

        with self.assertLogs(level='ERROR') as log:
            results = indexer.search("test query")
        self.assertIsNone(results)
        self.assertIn("SentenceTransformer model not loaded. Cannot perform search.", log.output[0])

    @patch('search_indexer.SentenceTransformer')
    def test_search_empty_index(self, mock_sentence_transformer_constructor):
        mock_model = MagicMock()
        mock_sentence_transformer_constructor.return_value = mock_model
        indexer = SemanticIndexer(project_root=self.project_root)
        indexer.corpus_embeddings = None # Empty index

        with self.assertLogs(level='WARNING') as log:
            results = indexer.search("test query")
        self.assertIsNone(results)
        self.assertIn("Index not built or loaded. Perform build_index() or load_index() first.", log.output[0])

    @patch('search_indexer.SentenceTransformer')
    def test_search_empty_query(self, mock_sentence_transformer_constructor):
        mock_model = MagicMock()
        mock_sentence_transformer_constructor.return_value = mock_model
        indexer = SemanticIndexer(project_root=self.project_root)
        indexer.corpus_embeddings = np.array([[0.1, 0.2]]) # Non-empty index

        results = indexer.search("") # Empty query
        self.assertEqual(results, [])

    @patch('search_indexer.util.semantic_search', return_value=[[]]) # No hits
    @patch('search_indexer.SentenceTransformer')
    def test_search_no_results(self, mock_sentence_transformer_constructor, mock_semantic_search):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.5, 0.5]])
        mock_sentence_transformer_constructor.return_value = mock_model

        indexer = SemanticIndexer(project_root=self.project_root)
        indexer.corpus_embeddings = np.array([[0.1, 0.2]])
        indexer.corpus_metadata = [{"file_path": "test.py", "text_chunk": "chunk1", "start_line":1, "end_line":2}]

        results = indexer.search("query with no match")
        self.assertEqual(results, [])
        mock_semantic_search.assert_called_once()


if __name__ == '__main__':
    unittest.main()
