# -*- coding: utf-8 -*-
import re
import os
from typing import List, Dict, Any
import pypdf
import docx
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Intentamos importar BeautifulSoup si está disponible
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

class DocumentProcessor:
    def __init__(self, min_chunk_size: int = 300, max_chunk_size: int = 1500, threshold: float = 0.15):
        """
        Inicializa el procesador de documentos y URLs.
        :param min_chunk_size: Tamaño mínimo en caracteres de un fragmento.
        :param max_chunk_size: Tamaño máximo en caracteres de un fragmento.
        :param threshold: Umbral de similitud coseno TF-IDF para dividir fragmentos semánticamente.
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.threshold = threshold

    def extract_text_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extrae el texto de un PDF manteniendo el número de página.
        """
        pages_content = []
        with open(file_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                text = text.strip()
                if text:
                    pages_content.append({
                        "text": text,
                        "page_number": i + 1
                    })
        return pages_content

    def extract_text_docx(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extrae el texto de un archivo Word (.docx).
        """
        doc = docx.Document(file_path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        
        sections = []
        current_section_text = []
        current_len = 0
        section_idx = 1
        
        for p in paragraphs:
            current_section_text.append(p)
            current_len += len(p)
            if current_len >= 2000:
                sections.append({
                    "text": "\n\n".join(current_section_text),
                    "page_number": section_idx
                })
                current_section_text = []
                current_len = 0
                section_idx += 1
                
        if current_section_text:
            sections.append({
                "text": "\n\n".join(current_section_text),
                "page_number": section_idx
            })
            
        return sections

    def extract_text_url(self, url: str) -> List[Dict[str, Any]]:
        """
        Extrae y limpia el contenido de texto de una página web a partir de su URL.
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        resp.encoding = resp.apparent_encoding or 'utf-8'
        html_content = resp.text
        
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                script.decompose()
            text = soup.get_text(separator='\n')
        else:
            text = re.sub(r'<(script|style|nav|footer|header).*?>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '\n', text)
            
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)
        
        sections = []
        paragraphs = clean_text.split("\n")
        current_section = []
        current_len = 0
        section_idx = 1
        
        for p in paragraphs:
            current_section.append(p)
            current_len += len(p)
            if current_len >= 2000:
                sections.append({
                    "text": "\n".join(current_section),
                    "page_number": section_idx
                })
                current_section = []
                current_len = 0
                section_idx += 1
                
        if current_section:
            sections.append({
                "text": "\n".join(current_section),
                "page_number": section_idx
            })
            
        return sections

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Divide un texto largo en oraciones individuales utilizando expresiones regulares.
        """
        sentence_end = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s+')
        sentences = sentence_end.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def semantic_chunking(self, text_blocks: List[Dict[str, Any]], filename: str) -> List[Dict[str, Any]]:
        """
        Aplica chunking semántico agrupando oraciones adyacentes basándose en la similitud de su TF-IDF vectorizado.
        """
        chunks = []
        chunk_global_id = 0

        for block in text_blocks:
            text = block["text"]
            page_num = block["page_number"]
            
            sentences = self.split_into_sentences(text)
            if not sentences:
                continue
                
            if len(sentences) == 1:
                chunks.append({
                    "text": sentences[0],
                    "metadata": {
                        "filename": filename,
                        "chunk_id": f"{filename}_{chunk_global_id}",
                        "index": chunk_global_id,
                        "page_number": page_num
                    }
                })
                chunk_global_id += 1
                continue

            try:
                vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5))
                tfidf_matrix = vectorizer.fit_transform(sentences)
                
                similarities = []
                for i in range(len(sentences) - 1):
                    sim = cosine_similarity(tfidf_matrix[i], tfidf_matrix[i+1])[0][0]
                    similarities.append(sim)
            except Exception:
                similarities = [0.0] * (len(sentences) - 1)

            current_chunk_sentences = [sentences[0]]
            current_chunk_len = len(sentences[0])

            for i in range(len(sentences) - 1):
                next_sentence = sentences[i+1]
                sim = similarities[i]
                
                if current_chunk_len + len(next_sentence) > self.max_chunk_size:
                    chunks.append({
                        "text": " ".join(current_chunk_sentences),
                        "metadata": {
                            "filename": filename,
                            "chunk_id": f"{filename}_{chunk_global_id}",
                            "index": chunk_global_id,
                            "page_number": page_num
                        }
                    })
                    chunk_global_id += 1
                    current_chunk_sentences = [next_sentence]
                    current_chunk_len = len(next_sentence)
                elif current_chunk_len < self.min_chunk_size:
                    current_chunk_sentences.append(next_sentence)
                    current_chunk_len += len(next_sentence) + 1
                else:
                    if sim >= self.threshold:
                        current_chunk_sentences.append(next_sentence)
                        current_chunk_len += len(next_sentence) + 1
                    else:
                        chunks.append({
                            "text": " ".join(current_chunk_sentences),
                            "metadata": {
                                "filename": filename,
                                "chunk_id": f"{filename}_{chunk_global_id}",
                                "index": chunk_global_id,
                                "page_number": page_num
                            }
                        })
                        chunk_global_id += 1
                        current_chunk_sentences = [next_sentence]
                        current_chunk_len = len(next_sentence)

            if current_chunk_sentences:
                chunks.append({
                    "text": " ".join(current_chunk_sentences),
                    "metadata": {
                        "filename": filename,
                        "chunk_id": f"{filename}_{chunk_global_id}",
                        "index": chunk_global_id,
                        "page_number": page_num
                    }
                })
                chunk_global_id += 1

        return chunks

    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Procesa el archivo según su extensión y retorna la lista de fragmentos indexables.
        """
        filename = os.path.basename(file_path)
        ext = filename.lower().split('.')[-1]
        
        if ext == 'pdf':
            blocks = self.extract_text_pdf(file_path)
        elif ext in ['docx', 'doc']:
            blocks = self.extract_text_docx(file_path)
        else:
            raise ValueError(f"Extensión de archivo no soportada: {ext}")
            
        return self.semantic_chunking(blocks, filename)

    def process_url(self, url: str) -> List[Dict[str, Any]]:
        """
        Scrapea una página web y la convierte en fragmentos semánticamente agrupados.
        """
        blocks = self.extract_text_url(url)
        clean_name = url.replace("https://", "").replace("http://", "").rstrip("/")
        clean_name = re.sub(r'[^\w\.-]', '_', clean_name)
        if len(clean_name) > 60:
            clean_name = clean_name[:60]
        filename = f"WEB_{clean_name}"
        return self.semantic_chunking(blocks, filename)
