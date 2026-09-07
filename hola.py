from __future__ import annotations

import json
import os
import argparse
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS


APP_DIR = Path(__file__).resolve().parent
ONTOLOGY_PATH = APP_DIR / "ontologia-la-sazon-197272-193042.owx"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


def local_name(value: URIRef | Literal) -> str:
	"""Returns a readable name from an RDF URI or literal."""
	text = str(value)
	return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def load_ontology(path: str) -> Graph:
	root = ElementTree.parse(path).getroot()
	graph = Graph()
	base = root.attrib.get("ontologyIRI", "")
	prefixes = {
		node.attrib["name"]: node.attrib["IRI"]
		for node in root
		if node.tag.rsplit("}", 1)[-1] == "Prefix"
	}

	def resource(node: ElementTree.Element) -> URIRef:
		iri = node.attrib.get("IRI")
		abbreviated = node.attrib.get("abbreviatedIRI")
		if iri is not None:
			return URIRef(urljoin(f"{base}/", iri.lstrip("#")))
		if abbreviated is not None:
			prefix, _, suffix = abbreviated.partition(":")
			return URIRef(prefixes.get(prefix, "") + suffix)
		raise ValueError(f"Nodo OWL/XML sin IRI: {node.tag}")

	for axiom in root:
		tag = axiom.tag.rsplit("}", 1)[-1]
		children = list(axiom)
		if tag == "Declaration" and children:
			entity = children[0]
			kind = entity.tag.rsplit("}", 1)[-1]
			types = {
				"Class": OWL.Class,
				"ObjectProperty": OWL.ObjectProperty,
				"DataProperty": OWL.DatatypeProperty,
				"NamedIndividual": OWL.NamedIndividual,
			}
			if kind in types:
				graph.add((resource(entity), RDF.type, types[kind]))
		elif tag == "SubClassOf" and len(children) >= 2:
			graph.add((resource(children[0]), RDFS.subClassOf, resource(children[1])))
		elif tag in {"ObjectPropertyDomain", "DataPropertyDomain"} and len(children) >= 2:
			graph.add((resource(children[0]), RDFS.domain, resource(children[1])))
		elif tag in {"ObjectPropertyRange", "DataPropertyRange"} and len(children) >= 2:
			graph.add((resource(children[0]), RDFS.range, resource(children[1])))
	return graph


def ontology_snapshot(graph: Graph, max_items: int = 100) -> dict[str, Any]:
	classes = sorted(
		{local_name(subject) for subject in graph.subjects(RDF.type, OWL.Class)}
	)
	object_properties = sorted(
		{
			local_name(subject)
			for subject in graph.subjects(RDF.type, OWL.ObjectProperty)
		}
	)
	data_properties = sorted(
		{local_name(subject) for subject in graph.subjects(RDF.type, OWL.DatatypeProperty)}
	)
	individuals = sorted(
		{
			local_name(subject)
			for subject in graph.subjects(RDF.type, OWL.NamedIndividual)
		}
	)
	if not individuals:
		individuals = sorted(
			{
				local_name(subject)
				for subject in graph.subjects()
				if isinstance(subject, URIRef)
				and not str(subject).startswith(str(OWL))
				and subject not in {RDF.type, RDFS.label}
			}
		)[:max_items]
	return {
		"clases": classes[:max_items],
		"propiedades_objeto": object_properties[:max_items],
		"propiedades_dato": data_properties[:max_items],
		"individuos": individuals[:max_items],
		"triples": len(graph),
	}


def compact_context(graph: Graph, snapshot: dict[str, Any], limit: int = 180) -> str:
	lines = [
		f"Clases: {', '.join(snapshot['clases']) or 'ninguna'}",
		f"Propiedades de relación: {', '.join(snapshot['propiedades_objeto']) or 'ninguna'}",
		f"Propiedades de datos: {', '.join(snapshot['propiedades_dato']) or 'ninguna'}",
		f"Entidades: {', '.join(snapshot['individuos']) or 'ninguna'}",
		"Afirmaciones relevantes:",
	]
	for subject, predicate, obj in list(graph)[:limit]:
		lines.append(f"- {local_name(subject)} --{local_name(predicate)}--> {local_name(obj)}")
	return "\n".join(lines)


def stream_ollama(
	base_url: str, model: str, messages: list[dict[str, str]]
) -> Iterator[str]:
	response = requests.post(
		f"{base_url.rstrip('/')}/api/chat",
		json={"model": model, "messages": messages, "stream": True},
		stream=True,
		timeout=(10, 300),
	)
	response.raise_for_status()
	for line in response.iter_lines():
		if not line:
			continue
		payload = json.loads(line.decode("utf-8"))
		content = payload.get("message", {}).get("content", "")
		if content:
			yield content


def build_prompt(question: str, context: str) -> str:
	return f"""Eres el asistente de conocimiento del restaurante La Sazón.
Responde en español, con claridad y brevedad, usando exclusivamente la ontología proporcionada.
Puedes explicar relaciones entre conceptos y señalar cuando la ontología no contiene suficiente información.
No inventes datos. No describas tu razonamiento interno; entrega solo una justificación breve basada en entidades o relaciones encontradas.

CONTEXTO DE LA ONTOLOGÍA:
{context}

PREGUNTA DEL USUARIO:
{question}

FORMATO:
Respuesta directa.
Fuente ontológica: menciona las clases, propiedades o entidades relevantes, si existen.
"""


def print_steps(snapshot: dict[str, Any], context: str, question: str) -> None:
	print("\n[1/4] Pregunta recibida")
	print(f"      {question}")
	print("[2/4] Ontología cargada")
	print(
		f"      {snapshot['triples']} triples, {len(snapshot['clases'])} clases y "
		f"{len(snapshot['propiedades_objeto']) + len(snapshot['propiedades_dato'])} propiedades"
	)
	print("[3/4] Contexto preparado")
	print(f"      {len(context):,} caracteres enviados a Ollama")
	print("[4/4] Inferencia en curso")
	print("      Respuesta en streaming:\n")


def parse_arguments() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Asistente ontológico de La Sazón")
	parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo de Ollama")
	parser.add_argument(
		"--ollama-url",
		default=os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_URL),
		help="URL base de Ollama",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_arguments()
	print("=" * 64)
	print("LA SAZÓN | Asistente ontológico con Ollama")
	print("Escribe 'salir' para terminar o 'ayuda' para ver ejemplos.")
	print("=" * 64)

	if not ONTOLOGY_PATH.exists():
		print(f"\nError: no se encontró la ontología en {ONTOLOGY_PATH}")
		return
	try:
		graph = load_ontology(str(ONTOLOGY_PATH))
	except Exception as exc:
		print(f"\nError al leer la ontología OWL/XML: {exc}")
		return

	snapshot = ontology_snapshot(graph)
	context = compact_context(graph, snapshot)
	print(
		f"Ontología lista: {snapshot['triples']} triples | "
		f"{len(snapshot['clases'])} clases | "
		f"{len(snapshot['propiedades_objeto'])} relaciones\n"
	)

	while True:
		try:
			question = input("Tú > ").strip()
		except (EOFError, KeyboardInterrupt):
			print("\nHasta luego.")
			break
		if not question:
			continue
		if question.lower() in {"salir", "exit", "quit"}:
			print("Hasta luego.")
			break
		if question.lower() == "ayuda":
			print("Ejemplos: ¿Qué roles trabajan en cocina? | ¿Qué espacios existen?")
			continue

		print_steps(snapshot, context, question)
		try:
			answer = ""
			for token in stream_ollama(
				args.ollama_url,
				args.model,
				[{"role": "user", "content": build_prompt(question, context)}],
			):
				print(token, end="", flush=True)
				answer += token
			print(f"\n\nModelo: {args.model} | Inferencia completada\n")
		except requests.exceptions.ConnectionError:
			print(
			f"\nNo se pudo conectar con Ollama en {args.ollama_url}. "
			f"Ejecuta 'ollama serve' y verifica que '{args.model}' esté instalado.\n"
			)
		except requests.exceptions.HTTPError as exc:
			print(f"\nOllama rechazó la solicitud: {exc}\n")
		except Exception as exc:
			print(f"\nError durante la inferencia: {exc}\n")


if __name__ == "__main__":
	main()
