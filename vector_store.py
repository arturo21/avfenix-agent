# -*- coding: utf-8 -*-
import pickle
import os
from typing import List, Dict, Any, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class SimpleVectorStore:
    def __init__(self, storage_path: str = "vector_index.pkl"):
        """
        Base vectorial local extremadamente rápida y 100% offline.
        Utiliza TF-IDF con n-gramas a nivel de palabras y caracteres para máxima tolerancia de términos.
        """
        self.storage_path = storage_path
        self.chunks: List[Dict[str, Any]] = []
        self.vectorizer: TfidfVectorizer = TfidfVectorizer(
            analyzer='word',
            ngram_range=(1, 2),
            stop_words=None, # Mantenemos stop words para conservar cohesión en frases cortas de soporte
            sublinear_tf=True
        )
        self.tfidf_matrix = None
        self.load()

    def load(self):
        """
        Carga la base de datos desde el archivo persistente si existe.
        """
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'rb') as f:
                    data = pickle.load(f)
                    self.chunks = data.get("chunks", [])
                    # Re-entrenamos el vectorizador si hay fragmentos cargados
                    self._rebuild_index()
            except Exception as e:
                print(f"Error cargando base vectorial persistente: {e}")
                self.chunks = []
                self.tfidf_matrix = None

    def save(self):
        """
        Guarda la base de datos actual en disco.
        """
        try:
            with open(self.storage_path, 'wb') as f:
                pickle.dump({"chunks": self.chunks}, f)
        except Exception as e:
            print(f"Error guardando base vectorial persistente: {e}")

    def _rebuild_index(self):
        """
        Reconstruye la matriz TF-IDF con los textos actuales en self.chunks.
        """
        if not self.chunks:
            self.tfidf_matrix = None
            return

        texts = [chunk["text"] for chunk in self.chunks]
        try:
            self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        except Exception as e:
            print(f"Error reconstruyendo el índice vectorial: {e}")
            self.tfidf_matrix = None

    def add_chunks(self, new_chunks: List[Dict[str, Any]]):
        """
        Añade nuevos fragmentos de conocimiento al índice, evitando duplicados.
        """
        existing_ids = {c["metadata"]["chunk_id"] for c in self.chunks}
        
        added_count = 0
        for chunk in new_chunks:
            if chunk["metadata"]["chunk_id"] not in existing_ids:
                self.chunks.append(chunk)
                added_count += 1
                
        if added_count > 0:
            self._rebuild_index()
            self.save()
            
        print(f"Añadidos {added_count} fragmentos nuevos a la base de conocimiento.")

    def delete_by_filename(self, filename: str) -> int:
        """
        Elimina todos los fragmentos asociados a un archivo específico.
        """
        initial_len = len(self.chunks)
        self.chunks = [c for c in self.chunks if c["metadata"]["filename"] != filename]
        deleted_count = initial_len - len(self.chunks)
        
        if deleted_count > 0:
            self._rebuild_index()
            self.save()
            
        print(f"Eliminados {deleted_count} fragmentos pertenecientes a '{filename}'.")
        return deleted_count

    def list_documents(self) -> List[str]:
        """
        Devuelve una lista única de los nombres de archivos cargados.
        """
        filenames = {c["metadata"]["filename"] for c in self.chunks}
        return sorted(list(filenames))

    def query(self, query_text: str, top_k: int = 4) -> List[Tuple[Dict[str, Any], float]]:
        """
        Busca los top_k fragmentos más relevantes para una consulta dada.
        Retorna una lista de tuplas (fragmento, puntuación_de_similitud).
        """
        if not self.chunks or self.tfidf_matrix is None:
            return []

        try:
            # Transformamos la consulta al espacio vectorial del corpus
            query_vector = self.vectorizer.transform([query_text])
            
            # Calculamos la similitud coseno de la consulta contra todos los chunks
            similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
            
            # Obtenemos los índices de mayor a menor similitud
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                # Solo consideramos fragmentos con alguna relevancia mínima (por ej. > 0.0)
                if score > 0.0:
                    results.append((self.chunks[idx], score))
                    
            return results
        except Exception as e:
            print(f"Error realizando consulta vectorial: {e}")
            return []