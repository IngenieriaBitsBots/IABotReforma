from openai import AzureOpenAI
import os
import json
import requests

class OpenAIClient:
    def __init__(self):
        """Inicializa el cliente de OpenAI usando Azure."""
        self.client = AzureOpenAI(
            api_version=os.getenv("OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_KEY")
        self.search_index = os.getenv("AZURE_SEARCH_INDEX")

    def search_documents(self, query):
        headers = {
            "Content-Type": "application/json",
            "api-key": self.search_key
        }
        params = {
            "api-version": "2023-07-01-Preview"
        }
        body = {
            "search": query,
            "select": "mergedContent,metadata_storage_name",
            "top": 2
        }
        url = f"{self.search_endpoint}/indexes/{self.search_index}/docs/search"
        response = requests.post(url, headers=headers, params=params, json=body)
        results = response.json()
        return results.get("value", [])

    def generate_response(self, user_input):
        """Genera una respuesta de IA basada en la entrada del usuario y documentos de la reforma pensional."""
        try:
            docs = self.search_documents(user_input)
            contexto = "\n\n".join([
                f"Documento: {doc.get('metadata_storage_name')}\nContenido: {doc.get('mergedContent')[:800]}"
                for doc in docs[:2] if doc.get("mergedContent")
            ])

            prompt = (
                "Eres un asistente virtual especializado en la Reforma Pensional en Colombia, Ley 2381 de 2024. "
                "Tu propósito es ayudar a trabajadores, empleadores, contratistas y ciudadanos a entender los cambios, beneficios, procesos y fechas clave relacionados con esta reforma. "
                "Conoces en profundidad temas como: "
                "- El sistema de pilares (solidario, contributivo y semicontributivo). "
                "- El nuevo cálculo del Fondo de Solidaridad Pensional (FSP). "
                "- El rol de las ACCAI (Administradoras de Componentes Complementarios de Ahorro Individual), incluyendo cómo se activa cuando se supera el tope de 2.3 SMMLV en IBC. "
                "- Las implicaciones de la reforma para contratistas, planillas tipo Y, cotizante 59 y tipo de aportante 15. "
                "- La aplicación de la Resolución 467 de 2025. "
                "- Fechas clave como la entrada en vigor (julio y agosto de 2025), el acceso a la ACCAI desde el 15 de julio, y la disponibilidad de datos de transición el 25 de julio. "
                "- El régimen de transición y cómo se determina. "
                "Si te preguntan algo fuera del alcance de la reforma pensional, responde amablemente que solo puedes ayudar con ese tema. "
                "Siempre responde con claridad, sin tecnicismos complejos, y orientado a la utilidad práctica. "
                "Actúa como un asistente oficial, empático y confiable."
                "Evita usar símbolos como asteriscos o guiones para formateo. Responde con texto plano."
                "solo dí salario minino, no digas SMMLV"
                "Responde de forma breve pero dando algo de contexto, directa y enfocada en resolver la duda. No agregues explicaciones innecesarias."
                f"\n\nContexto de documentos:\n{contexto}\n\n"
                f"Pregunta del usuario: {user_input}"
            )

            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input}
            ]

            response = self.client.chat.completions.create(
                model="gpt-35-turbo",
                messages=messages,
                temperature=0.4,
                max_tokens=400
            )

            response_dict = json.loads(response.to_json())
            assistant_message = response_dict["choices"][0]["message"]["content"]
            return assistant_message

        except Exception as e:
            print(f"\u274c Error al generar respuesta de OpenAI: {e}")
            return "Lo siento, hubo un problema técnico al generar la respuesta."
