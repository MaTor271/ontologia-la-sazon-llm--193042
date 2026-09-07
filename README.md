# La Sazón · asistente ontológico con Ollama

Asistente interactivo de consola para consultar en lenguaje natural la ontología OWL/XML de La Sazón. La aplicación carga `ontologia-la-sazon-197272-193042.owx`, prepara un contexto con sus clases, propiedades y afirmaciones, y usa Ollama con el modelo `llama3.2` para generar respuestas en español.

## Características

- Consola interactiva con consultas consecutivas durante la sesión.
- Streaming de la respuesta token a token.
- Trazabilidad visible de la consulta: pregunta recibida, ontología analizada, contexto preparado e inferencia en curso.
- Respuestas restringidas al contenido de la ontología, con indicación de fuentes ontológicas relevantes.
- Resumen inicial con cantidad de triples, clases, relaciones y entidades detectadas.
- URL de Ollama y modelo configurables mediante argumentos de terminal.

## Requisitos

- Python 3.10 o superior.
- Ollama instalado y ejecutándose localmente.
- El modelo `llama3.2` descargado.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.2
```

En Windows, activa el entorno con `.venv\\Scripts\\activate`.

## Ejecución

En una terminal, inicia Ollama si todavía no está activo:

```bash
ollama serve
```

En otra terminal, desde este directorio, ejecuta:

```bash
streamlit run hola.py
```

Inicia la consola desde este directorio:

```bash
python hola.py
```

Escribe una pregunta y observa los pasos de trazabilidad mientras Ollama responde. Usa `salir` para terminar y `ayuda` para ver ejemplos.

## Configuración

Los argumentos permiten cambiar:

- **URL de Ollama**: `python hola.py --ollama-url http://localhost:11434`. También se puede establecer con la variable `OLLAMA_HOST`.
- **Modelo**: `python hola.py --model llama3.2`. Debe existir en Ollama, por ejemplo con `ollama pull llama3.2`.

La ontología debe permanecer junto a `hola.py` con el nombre `ontologia-la-sazon-197272-193042.owx`.

## Ejemplos de preguntas

- ¿Qué roles trabajan en cocina?
- ¿Qué propiedades relacionan un pedido con sus elementos?
- ¿Qué tipos de espacios existen en el restaurante?
- ¿Qué información conoce la ontología sobre un proveedor?

## Nota sobre la retroalimentación

La trazabilidad de consola describe las etapas de preparación y ejecución de la consulta. No muestra el razonamiento privado del modelo: Ollama solo devuelve la respuesta final y una referencia breve a las entidades o relaciones utilizadas.
