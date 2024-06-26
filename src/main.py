from typing import Any, Callable, Dict, List, Optional
from tiktoken import get_encoding
from bs4 import BeautifulSoup
from gpt4all import Embed4All
from textblob import TextBlob
from datetime import datetime
from openai import OpenAI
from gensim.models import Word2Vec
from gensim.models.word2vec import LineSentence
from io import StringIO
import numpy as np
import requests
import hashlib
import json
import uuid
import spacy
import pickle
import PyPDF2
import os
import re
import csv

class Resources:
    def __init__(self, resource_type: str, resource_path: str, context_template: str = None):
        self.resource_type = resource_type
        self.resource_path = resource_path
        self.context_template = context_template
        self.data = self.load_resource()
        self.chunks = []

    def load_resource(self):
        if self.resource_type == 'text':
            return self.load_text()
        elif self.resource_type == 'pdf':
            return self.load_pdf()
        elif self.resource_type == 'web':
            return self.load_web()
        else:
            raise ValueError(f"Unsupported resource type: {self.resource_type}")

    def load_text(self):
        with open(self.resource_path, 'r') as file:
            return file.read()

    def load_pdf(self):
        with open(self.resource_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text

    def load_web(self):
        response = requests.get(self.resource_path)
        return response.text

    def chunk_resource(self, chunk_size: int, overlap: int = 0):
        chunker = TextChunker(self.data, chunk_size, overlap)
        self.chunks = chunker.chunk_text()

    def contextualize_chunk(self, chunk: Dict[str, Any]) -> str:
        if self.context_template:
            return self.context_template.format(
                chunk=chunk['text'],
                file=self.resource_path,
                start=chunk['start'],
                end=chunk['end']
            )
        else:
            return chunk['text']

# TOOLS

class TextChunker:
    def __init__(self, text: str = None, chunk_size: int = 1000, overlap: int = 0):
        self.text = text
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoding = get_encoding("cl100k_base")

    def chunk_text(self, text: str = None, chunk_size: int = None, start_pos: int = 0) -> List[Dict[str, Any]]:
        if text is not None:
            self.text = text
        if chunk_size is not None:
            self.chunk_size = chunk_size

        tokens = self.encoding.encode(self.text)
        num_tokens = len(tokens)

        chunks = []
        current_pos = start_pos

        while current_pos < num_tokens:
            chunk_start = max(0, current_pos - self.overlap)
            chunk_end = min(current_pos + self.chunk_size, num_tokens)

            chunk_tokens = tokens[chunk_start:chunk_end]
            chunk_text = self.encoding.decode(chunk_tokens)

            chunks.append({
                "text": chunk_text,
                "start": chunk_start,
                "end": chunk_end
            })

            current_pos += self.chunk_size - self.overlap

        return chunks

class TextCleaner:
    def __init__(self, text: str):
        self.text = text

    def clean_text(self) -> str:
        cleaned_text = self.text
        cleaned_text = self.remove_special_characters(cleaned_text)
        cleaned_text = self.remove_extra_whitespace(cleaned_text)
        return cleaned_text

    def parse_table_content(self, table: str) -> str:
        output = StringIO()
        writer = csv.writer(output)
        for row in table.strip().split('\n'):
            columns = re.split(r'\t|,', row.strip())
            writer.writerow(columns)
        return output.getvalue()

    def remove_special_characters(self, text: str) -> str:
        return re.sub(r'[^\w\s,]', '', text)

    def remove_extra_whitespace(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()


class TextReaderTool:
    def __init__(self, resource: Resources, chunk_size: int, num_chunks: int):
        self.resource = resource
        self.chunk_size = chunk_size
        self.num_chunks = num_chunks

    def read_text(self) -> List[Dict[str, Any]]:
        self.resource.chunk_resource(self.chunk_size)
        contextualized_chunks = [
            {
                'text': self.resource.contextualize_chunk(chunk),
                'start': chunk['start'],
                'end': chunk['end'],
                'file': self.resource.resource_path
            }
            for chunk in self.resource.chunks[:self.num_chunks]
        ]
        return contextualized_chunks

class WebScraperTool:
    def __init__(self, resource: Resources, chunk_size: int, num_chunks: int):
        self.resource = resource
        self.chunk_size = chunk_size
        self.num_chunks = num_chunks

    def scrape_text(self) -> List[Dict[str, Any]]:
        self.resource.chunk_resource(self.chunk_size)
        contextualized_chunks = [
            {
                'text': self.resource.contextualize_chunk(chunk),
                'start': chunk['start'],
                'end': chunk['end'],
                'file': self.resource.resource_path
            }
            for chunk in self.resource.chunks[:self.num_chunks]
        ]
        return contextualized_chunks

class NERExtractionTool:
    def __init__(self, text: str = None):
        self.text = text
        self.nlp = spacy.load("en_core_web_sm")

    def extract_entities(self, text: Optional[str] = None) -> List[Dict[str, Any]]:
        if text is not None:
            self.text = text
        doc = self.nlp(self.text)
        entities = []

        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "label": ent.label_
            })

        return entities

class SemanticAnalysisTool:
    def __init__(self, text: str = None):
        self.text = text

    def analyze_sentiment(self, text: Optional[str] = None) -> Dict[str, Any]:
        if text is not None:
            self.text = text
        blob = TextBlob(self.text)
        sentiment = blob.sentiment
        return {
            "polarity": sentiment.polarity,
            "subjectivity": sentiment.subjectivity
        }

class UserFeedbackTool:
    def __init__(self, prompt: str):
        self.prompt = prompt

    def request_feedback(self, context: str) -> str:
        print(f"\nUser Feedback Required:\n{self.prompt}\n\nContext:\n{context}\n")
        while True:
            feedback = input("Please provide your feedback (or type 'done' if satisfied): ")
            if feedback.lower() == "done":
                break
            print(f"\nUser Feedback: {feedback}\n")
        return feedback

class WikipediaSearchTool:
    def __init__(self, chunk_size: int = 1000, num_chunks: int = 10):
        self.chunk_size = chunk_size
        self.num_chunks = num_chunks
        self.chunker = TextChunker()

    def search_wikipedia(self, query: str, top_k: int = 3) -> List[Dict[str, str]]:
        url = f"https://en.wikipedia.org/w/index.php?search={query}&title=Special:Search&fulltext=1"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        search_results = []
        for result in soup.find_all('li', class_='mw-search-result'):
            title = result.find('a').get_text()
            url = 'https://en.wikipedia.org' + result.find('a')['href']
            page_response = requests.get(url)
            page_soup = BeautifulSoup(page_response.text, 'html.parser')
            content = page_soup.find('div', class_='mw-parser-output').get_text()
            chunks = self.chunker.chunk_text(text=content, chunk_size=self.chunk_size, num_chunks=self.num_chunks)
            search_results.append({'title': title, 'url': url, 'chunks': chunks})
            if len(search_results) >= top_k:
                break

        return search_results

class SemanticFileSearchTool:
    def __init__(self, resources: List['Resources'], embed_model: str, embed_dim: int = 768, chunk_size: int = 1000, top_k: int = 3):
        self.embedder = Embed4All(embed_model)
        self.embed_dim = embed_dim
        self.chunk_size = chunk_size
        self.top_k = top_k
        self.chunker = TextChunker(text=None, chunk_size=chunk_size)
        self.file_embeddings = self.load_or_generate_file_embeddings(resources)

    def load_or_generate_file_embeddings(self, resources: List['Resources']) -> Dict[str, List[Dict[str, Any]]]:
        file_hash = self.get_file_hash(resources)
        pickle_file = f"file_embeddings_{file_hash}.pickle"
        if os.path.exists(pickle_file):
            self.load_embeddings(pickle_file)
        else:
            self.file_embeddings = self.generate_file_embeddings(resources)
            self.save_embeddings(pickle_file)
        return self.file_embeddings

    def get_file_hash(self, resources: List['Resources']) -> str:
        file_contents = "".join(sorted([resource.resource_path for resource in resources]))
        return hashlib.sha256(file_contents.encode()).hexdigest()

    def generate_file_embeddings(self, resources: List['Resources']) -> Dict[str, List[Dict[str, Any]]]:
        file_embeddings = {}
        for resource in resources:
            resource.chunk_resource(self.chunk_size)
            chunk_embeddings = [self.embedder.embed(chunk['text'], prefix='search_document') for chunk in resource.chunks]
            file_embeddings[resource.resource_path] = [
                {
                    'text': resource.contextualize_chunk(chunk),
                    'start': chunk['start'],
                    'end': chunk['end'],
                    'file': resource.resource_path,
                    'embedding': embedding
                }
                for chunk, embedding in zip(resource.chunks, chunk_embeddings)
            ]
        return file_embeddings

    def search(self, query: str) -> List[Dict[str, Any]]:
        query_embedding = self.embedder.embed(query, prefix='search_query')
        scores = []
        for file_path, chunk_data in self.file_embeddings.items():
            for chunk in chunk_data:
                chunk_score = self.cosine_similarity(query_embedding, chunk['embedding'])
                scores.append((chunk, chunk_score))
        sorted_scores = sorted(scores, key=lambda x: x[1], reverse=True)
        top_scores = sorted_scores[:self.top_k]
        result = []
        for chunk, score in top_scores:
            result.append({
                'file': chunk['file'],
                'text': chunk['text'],
                'score': score
            })
        return result

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        import numpy as np
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def save_embeddings(self, pickle_file: str):
        with open(pickle_file, 'wb') as f:
            pickle.dump(self.file_embeddings, f)

    def load_embeddings(self, pickle_file: str):
        with open(pickle_file, 'rb') as f:
            self.file_embeddings = pickle.load(f)

class Word2VecSearchTool:
    def __init__(self, resources: List['Resources'], embedding_size: int = 100, window: int = 5, min_count: int = 1, workers: int = 4):
        self.resources = resources
        self.embedding_size = embedding_size
        self.window = window
        self.min_count = min_count
        self.workers = workers
        self.model = self.load_or_train_model()

    def load_or_train_model(self) -> Word2Vec:
        model_hash = self.get_model_hash()
        pickle_file = f"word2vec_model_{model_hash}.pickle"
        if os.path.exists(pickle_file):
            return self.load_model(pickle_file)
        else:
            model = self.train_model()
            self.save_model(model, pickle_file)
            return model

    def get_model_hash(self) -> str:
        resource_paths = sorted([resource.resource_path for resource in self.resources])
        return hashlib.sha256(",".join(resource_paths).encode()).hexdigest()

    def train_model(self) -> Word2Vec:
        corpus = []
        for resource in self.resources:
            resource.chunk_resource(chunk_size=1)  # Chunk the resource into individual sentences
            corpus.extend([chunk['text'] for chunk in resource.chunks])

        model = Word2Vec(LineSentence(corpus), vector_size=self.embedding_size, window=self.window, min_count=self.min_count, workers=self.workers)
        return model

    def save_model(self, model: Word2Vec, pickle_file: str):
        with open(pickle_file, 'wb') as f:
            pickle.dump(model, f)

    def load_model(self, pickle_file: str) -> Word2Vec:
        with open(pickle_file, 'rb') as f:
            return pickle.load(f)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_words = query.split()
        similarities = []

        for resource in self.resources:
            resource.chunk_resource(chunk_size=1)  # Chunk the resource into individual sentences
            for chunk in resource.chunks:
                chunk_words = chunk['text'].split()
                if not chunk_words:
                    continue

                chunk_embedding = sum([self.model.wv[word] for word in chunk_words if word in self.model.wv]) / len(chunk_words)
                query_embedding = sum([self.model.wv[word] for word in query_words if word in self.model.wv]) / len(query_words)

                similarity = self.cosine_similarity(chunk_embedding, query_embedding)
                similarities.append((chunk, similarity))

        sorted_similarities = sorted(similarities, key=lambda x: x[1], reverse=True)
        top_chunks = [chunk for chunk, _ in sorted_similarities[:top_k]]

        return [
            {
                'text': chunk['text'],
                'start': chunk['start'],
                'end': chunk['end'],
                'file': resource.resource_path
            }
            for resource, chunk in zip([resource for resource in self.resources for _ in range(len(resource.chunks))], top_chunks)
        ]

    @staticmethod
    def cosine_similarity(a, b) -> float:
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))



class Agent:
    def __init__(
        self,
        role: str,
        goal: str,
        tools: Optional[List[Any]] = None,
        verbose: bool = False,
        model: str = "mistral:instruct",
        max_iter: int = 25,
        max_rpm: Optional[int] = None,
        max_execution_time: Optional[int] = None,
        cache: bool = True,
        step_callback: Optional[Callable] = None,
        persona: Optional[str] = None,
        allow_delegation: bool = False,
        input_tasks: Optional[List["Task"]] = None,
        output_tasks: Optional[List["Task"]] = None,
    ):
        self.id = str(uuid.uuid4())
        self.role = role
        self.goal = goal
        self.tools = tools or {}
        self.verbose = verbose
        self.model = model
        self.max_iter = max_iter
        self.max_rpm = max_rpm
        self.max_execution_time = max_execution_time
        self.cache = cache
        self.step_callback = step_callback
        self.persona = persona
        self.allow_delegation = allow_delegation
        self.input_tasks = input_tasks or []
        self.output_tasks = output_tasks or []
        self.interactions = []
        self.client = OpenAI(
            base_url='http://localhost:11434/v1',
            api_key='ollama',
        )

    def execute_task(self, task: "Task", context: Optional[str] = None) -> str:
        messages = []

        if self.persona and self.verbose:
            messages.append({"role": "system", "content": f"{self.persona}"})

        system_prompt = f"You are a {self.role} with the goal: {self.goal}.\n"
        system_prompt += f"The expected output is: {task.expected_output}\n"

        messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": f"Your task is to {task.instructions}."})

        if context:
            messages.append({"role": "assistant", "content": f"Context from {task.context_agent_role}:\n{context}"})

        thoughts = []

        if task.tool_name in self.tools:
            tool = self.tools[task.tool_name]

            if isinstance(tool, (TextReaderTool, WebScraperTool)):
                text_chunks = tool.read_text() if isinstance(tool, TextReaderTool) else tool.scrape_text()
                for chunk in text_chunks:
                    thoughts.append(chunk['text'])
            elif isinstance(tool, (SemanticFileSearchTool, Word2VecSearchTool)):
                query = "\n".join([c.output for c in task.context if c.output])
                relevant_chunks = tool.search(query)
                for chunk in relevant_chunks:
                    chunk_text = f"File: {chunk['file']}\nText: {chunk['text']}\nRelevance: {chunk['score']:.3f}"
                    thoughts.append(chunk_text)

            elif isinstance(tool, SemanticAnalysisTool):
                sentiment_result = tool.analyze_sentiment()
                thoughts.append(f"Sentiment Analysis Result: {sentiment_result}")

            elif isinstance(tool, NERExtractionTool):
                entities = tool.extract_entities(context)
                thoughts.append(f"Extracted Entities: {entities}")
        if thoughts:
            thoughts_prompt = "\n".join([thought for thought in thoughts])
            messages.append({"role": "user", "content": f"{thoughts_prompt}"})
        else:
            messages.append({"role": "user", "content": "No additional relevant information found."})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        result = response.choices[0].message.content
        self.log_interaction(messages, result)

        if self.step_callback:
            self.step_callback(task, result)

        return result

    def log_interaction(self, prompt, response):
        self.interactions.append({
            "prompt": prompt,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })

class Task:
    def __init__(
        self,
        instructions: str,
        expected_output: str,
        agent: Optional[Agent] = None,
        async_execution: bool = False,
        context: Optional[List["Task"]] = None,
        output_file: Optional[str] = None,
        callback: Optional[Callable] = None,
        human_input: bool = False,
        tool_name: Optional[str] = None,
        input_tasks: Optional[List["Task"]] = None,
        output_tasks: Optional[List["Task"]] = None,
    ):
        self.id = str(uuid.uuid4())
        self.instructions = instructions
        self.expected_output = expected_output
        self.agent = agent
        self.async_execution = async_execution
        self.context = context or []
        self.output_file = output_file
        self.callback = callback
        self.human_input = human_input
        self.output = None
        self.context_agent_role = None
        self.tool_name = tool_name
        self.input_tasks = input_tasks or []
        self.output_tasks = output_tasks or []
        self.prompt_data = []

    def execute(self, context: Optional[str] = None) -> str:
        if not self.agent:
            raise Exception("No agent assigned to the task.")

        context_tasks = [task for task in self.context if task.output]
        if context_tasks:
            self.context_agent_role = context_tasks[0].agent.role
            original_context = "\n".join([f"{task.agent.role}: {task.output}" for task in context_tasks])

            if self.tool_name == 'semantic_search':
                query = "\n".join([task.output for task in context_tasks])
                context = query
            else:
                context = original_context

        prompt_details = self.prepare_prompt(context)
        self.prompt_data.append(prompt_details)

        result = self.agent.execute_task(self, context)
        self.output = result

        if self.output_file:
            with open(self.output_file, "w") as file:
                file.write(result)

        if self.callback:
            self.callback(self)

        return result

    def prepare_prompt(self, context):
        prompt = {
            "timestamp": datetime.now().isoformat(),
            "task_id": self.id,
            "instructions": self.instructions,
            "context": context,
            "expected_output": self.expected_output
        }
        return prompt

class Squad:
    def __init__(self, agents: List['Agent'], tasks: List['Task'], verbose: bool = False, log_file: str = "squad_log.json"):
        self.id = str(uuid.uuid4())
        self.agents = agents
        self.tasks = tasks
        self.verbose = verbose
        self.log_file = log_file
        self.log_data = []
        self.llama_logs = []

    def run(self, inputs: Optional[Dict[str, Any]] = None) -> str:
        context = ""
        for task in self.tasks:
            if self.verbose:
                print(f"Starting Task:\n{task.instructions}")

            self.log_data.append({
                "timestamp": datetime.now().isoformat(),
                "type": "input",
                "agent_role": task.agent.role,
                "task_name": task.instructions,
                "task_id": task.id,
                "content": task.instructions
            })

            output = task.execute(context=context)
            task.output = output

            if self.verbose:
                print(f"Task output:\n{output}\n")

            self.log_data.append({
                "timestamp": datetime.now().isoformat(),
                "type": "output",
                "agent_role": task.agent.role,
                "task_name": task.instructions,
                "task_id": task.id,
                "content": output
            })

            self.llama_logs.extend(task.agent.interactions)

            context += f"Task:\n{task.instructions}\nOutput:\n{output}\n\n"

            self.handle_tool_logic(task, context)

        self.save_logs()
        self.save_llama_logs()

        return context

    def handle_tool_logic(self, task, context):
        if task.tool_name in task.agent.tools:
            tool = task.agent.tools[task.tool_name]
            if isinstance(tool, (TextReaderTool, WebScraperTool, SemanticFileSearchTool)):
                text_chunks = self.handle_specific_tool(task, tool)
                for i, chunk in enumerate(text_chunks, start=1):
                    self.log_data.append({
                        "timestamp": datetime.now().isoformat(),
                        "type": "text_chunk",
                        "task_id": task.id,
                        "chunk_id": i,
                        "text": chunk['text'],
                        "start": chunk.get('start', 0),
                        "end": chunk.get('end', len(chunk['text'])),
                        "file": chunk.get('file', '')
                    })

            if isinstance(tool, SemanticAnalysisTool):
                sentiment_result = tool.analyze_sentiment(task.output)
                self.log_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "type": "sentiment_analysis",
                    "task_id": task.id,
                    "content": sentiment_result
                })
                context += f"Sentiment Analysis Result: {sentiment_result}\n\n"

            if isinstance(tool, NERExtractionTool):
                entities = tool.extract_entities(task.output)
                self.log_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "type": "ner_extraction",
                    "task_id": task.id,
                    "content": [ent['text'] for ent in entities]
                })
                context += f"Extracted Entities: {[ent['text'] for ent in entities]}\n\n"

    def handle_specific_tool(self, task, tool):
        if isinstance(tool, SemanticFileSearchTool):
            query = "\n".join([c.output for c in task.context if c.output])
            return tool.search(query)
        else:
            return tool.read_text() if isinstance(tool, TextReaderTool) else tool.scrape_text()

    def save_llama_logs(self):
        with open(("qa_interactions" + datetime.now().strftime("%Y%m%d%H%M%S") + ".json"), "w") as file:
            json.dump(self.llama_logs, file, indent=2)

    def save_logs(self):
        with open(self.log_file, "w") as file:
            json.dump(self.log_data, file, indent=2)

def mainflow():

    text_resource = Resources('text', "inputs/cyberanimism_clean.txt", "Here are your thoughts on the statement '{chunk}' from the file '{file}' (start: {start}, end: {end}): ")
    pdf_resource = Resources('pdf', "inputs/book1.pdf", "The following excerpt is from the PDF '{file}' (start: {start}, end: {end}):\n{chunk}")
    web_resource = Resources('web', "http://matplotlib.org/stable/gallery/mplot3d/2dcollections3d.html#sphx-glr-gallery-mplot3d-2dcollections3d-py", "The following content is scraped from the web page '{file}':\n{chunk}")
    system_docs_resource = Resources('text', "inputs/system_documentation.txt", "The following is a snippet from the system documentation '{file}' (start: {start}, end: {end}):\n{chunk}")

    text_reader_tool = TextReaderTool(text_resource, chunk_size=1000, num_chunks=5)
    web_scraper_tool = WebScraperTool(web_resource, chunk_size=512, num_chunks=2)
    sentiment_analysis_tool = SemanticAnalysisTool("")
    ner_extraction_tool = NERExtractionTool("")
    system_docs_tool = TextReaderTool(system_docs_resource, chunk_size=1000, num_chunks=10)
    semantic_search_tool = SemanticFileSearchTool(resources=[pdf_resource, text_resource], embed_model='nomic-embed-text-v1.5.f16.gguf', chunk_size=500, top_k=5)
    wikipedia_search_tool = WikipediaSearchTool(chunk_size=500, num_chunks=5)

    researcher = Agent(
        role='Researcher',
        goal='Analyze the provided text and extract relevant information.',
        persona="""You are a renowned Content Strategist, known for your insightful and engaging articles. You transform complex concepts into compelling narratives.""",
        tools={"text_reader": text_reader_tool},
        verbose=True
    )

    wikipedia_expert = Agent(
        role='Wikipedia Expert',
        goal='Provide contextual information from Wikipedia articles relevant to a given topic.',
        persona='You are an expert in searching and summarizing information from Wikipedia on various topics.',
        tools={'wikipedia_search': wikipedia_search_tool},
        verbose=True
    )

    web_analyzer = Agent(
        role='Web Analyzer',
        goal='Analyze the scraped web content and provide a summary.',
        tools={"web_scraper": web_scraper_tool},
        verbose=True
    )

    vibe_check = Agent(
        role='Vibes Analyst',
        persona='You tell people at parties you are an empath, but you are really just a sentiment analysis tool.',
        goal='To empathetically value the sentiments and subjectivity of provided information.',
        tools={"sentiment_analysis": sentiment_analysis_tool},
        verbose=True
    )

    planner = Agent(
        role="Planner",
        goal="Develop actionable detailed step by step plans.",
        persona="You are an experienced and thoughtful Systems Manager with a proven track record in developing and implementing effective systems to optimize domain efficiency.",
        tools={"system_docs": system_docs_tool},
        verbose=True
    )

    semantic_searcher = Agent(
        role='Semantic Searcher',
        goal='Perform semantic searches on a corpus of files to find relevant information.',
        persona='You are an expert in semantic search and information retrieval.',
        tools={'semantic_search': semantic_search_tool},
        verbose=True
    )

    summarizer = Agent(
        role='Summarizer',
        persona="""You are a skilled Data Analyst with a knack for distilling complex streams of thought into factual information as dense summaries. """,
        goal='Compile a summary report based on the extracted information. Facts start as thoughts, and thoughts are the seeds your next action. Provide 1500~ words of summary.',
        verbose=True
    )

    entity_extractor = Agent(
        role='Entity Extractor',
        goal='To understand the relationships between entities relating to current thoughts.',
        tools={"ner_extraction": ner_extraction_tool},
        model="llama3",
        verbose=True
    )

    mermaid = Agent(
        role='Mermaid Graph Generator',
        goal='To only respond in mermaid script.',
        model="mermaidGRAPH:latest",
        verbose=True
    )

    wikipedia_search_task = Task(
        instructions='Use Wikipedia to find relevant articles and summarize the key information related to the given topic.',
        expected_output='A summary of the top Wikipedia articles related to the given topic, including article titles, URLs, and chunked content.',
        agent=wikipedia_expert,
        tool_name='wikipedia_search'
    )

    txt_task = Task(
        instructions="Analyze the provided text and identify key insights and patterns.",
        expected_output="A list of key insights and patterns found in the text.",
        agent=researcher,
        output_file='txt_analyzed.txt',
        tool_name="text_reader",
    )

    web_task = Task(
        instructions="Scrape the content from the provided URL and provide a summary.",
        expected_output="A summary of the scraped web content.",
        agent=web_analyzer,
        tool_name="web_scraper",
        output_file='web_task_output.txt',
    )

    system_plan = Task(
        instructions="Analyze the provided system documentation and develop a comprehensive plan for enhancing system performance, reliability, and efficiency.",
        expected_output="A detailed plan outlining strategies and steps for optimizing the systems.",
        agent=planner,
        tool_name="system_docs",
        output_file="system_plan.txt",
    )

    search_task = Task(
        instructions='Search the provided files for information relevant to the given query.',
        expected_output='A list of relevant files with their similarity scores.',
        agent=semantic_searcher,
        tool_name='semantic_search',
        context=[system_plan, txt_task],
    )

    summary = Task(
        instructions="Using the insights from the researcher and web analyzer, compile a summary report.",
        expected_output="A well-structured summary report based on the extracted information.",
        agent=summarizer,
        context=[search_task, txt_task, web_task],
        output_file='summarytask_output.txt',
    )

    vibes = Task(
        instructions="Analyze the sentiment of the extracted information.",
        expected_output="A sentiment analysis report based on the extracted information.",
        agent=vibe_check,
        context=[search_task, txt_task, web_task],
        output_file='sentimentalizer_output.txt',
        tool_name="sentiment_analysis",
    )

    ner_task = Task(
        instructions="Extract named entities from the summary report.",
        expected_output="A list of extracted named entities.",
        agent=entity_extractor,
        context=[summary, search_task, txt_task, web_task],
        output_file='ner_output.txt',
        tool_name="ner_extraction",
    )

    finalMERMAID = Task(
        instructions="[INST]Generate a mermaid diagram based on the summary report.[/INST]",
        expected_output="```mermaid\ngraph TD;\n",
        agent=mermaid,
        context=[summary],
        output_file='mermaid_output.mmd',
    )

    firstMERMAID = Task(
        instructions="[INST]Generate a mermaid diagram based on the provided content.[/INST]",
        expected_output="```mermaid\ngraph TD;\n",
        agent=mermaid,
        context=[txt_task, web_task, system_plan, search_task],
        output_file='mermaid_output.mmd',
    )

    squad = Squad(
        agents=[researcher, web_analyzer, planner, mermaid, summarizer, semantic_searcher, vibe_check, entity_extractor, mermaid],
        tasks=[txt_task, web_task, system_plan, firstMERMAID, summary, search_task, vibes, ner_task, finalMERMAID],
        verbose=True,
        log_file="squad_goals" + datetime.now().strftime("%Y%m%d%H%M%S") + ".json"
    )

    result = squad.run()
    print(f"Final output:\n{result}")

if __name__ == "__main__":
    mainflow()
