from quart import Quart, request, Response
from azure.communication.callautomation.aio import CallAutomationClient
from azure.communication.callautomation import (
    CallConnectionClient,
    PhoneNumberIdentifier,
    RecognizeInputType
)
from azure.communication.callautomation import SsmlSource
from azure.core.messaging import CloudEvent
from azure.eventgrid import EventGridEvent, SystemEventNames
from openia_client import OpenAIClient
import os
import logging
import uuid
from dotenv import load_dotenv
import asyncio
from collections import defaultdict
from hypercorn.asyncio import serve
from hypercorn.config import Config
import html

call_guid_to_caller = defaultdict(lambda: "+573000000000")
call_state = defaultdict(dict)  # estado por llamada

app = Quart(__name__, template_folder="template")
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Configuraciones desde variables de entorno
ACS_CONNECTION_STRING = os.getenv("ACS_CONNECTION_STRING")
ACS_PHONE_NUMBER = os.getenv("ACS_PHONE_NUMBER")
CALLBACK_URI_HOST = os.getenv("CALLBACK_URI_HOST")
CALLBACK_EVENTS_URI = CALLBACK_URI_HOST + "/api/callbacks"
COGNITIVE_SERVICES_ENDPOINT = os.getenv("COGNITIVE_SERVICES_ENDPOINT")

SPEECH_TO_TEXT_VOICE = "es-US-PalomaNeural"

call_automation_client = CallAutomationClient.from_connection_string(ACS_CONNECTION_STRING)


def check_exit_condition(text):
    return any(p in text.lower() for p in ["salir", "terminar", "adios", "hasta luego", "gracias", "chao"])

def normalizar_acronimos(text):
    if not text:
        return text
    text = text.lower()
    variantes_accai = ["accai", "acai", "akai", "accay", "akaí", "a c c a i", "a ce ce ai", "a ce ce a i"]
    for variante in variantes_accai:
        if variante in text:
            return text.replace(variante, "ACCAI")
    return text

async def answer_call(incoming_call_context, callback_url):
    return await call_automation_client.answer_call(
        incoming_call_context=incoming_call_context,
        callback_url=callback_url,
        cognitive_services_endpoint=COGNITIVE_SERVICES_ENDPOINT
    )

async def iniciar_reconocimiento(call_connection_client, target_participant):
    await call_connection_client.start_recognizing_media(
        input_type=RecognizeInputType.SPEECH,
        target_participant=target_participant,
        play_prompt=None,
        interrupt_prompt=True,
        initial_silence_timeout=6,
        end_silence_timeout=3,
        speech_language="es-CO",
        operation_context="reforma_loop"
    )

async def handle_play(call_connection_client: CallConnectionClient, text_to_play: str):
    sanitized_text = html.escape(text_to_play)
    ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
    xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="es-CO">
        <voice name="{SPEECH_TO_TEXT_VOICE}">
            <prosody rate="-15%">{sanitized_text}</prosody>
        </voice>
    </speak>"""
    ssml_source = SsmlSource(ssml_text=ssml)
    await call_connection_client.play_media_to_all(ssml_source)

async def handle_reforma_conversacion(call_connection_client: CallConnectionClient, call_connection_id: str, target_participant: PhoneNumberIdentifier):
    try:
        bienvenida = "Hola, soy tu asistente virtual para resolver dudas sobre la reforma pensional en Colombia. ¿Qué deseas saber?"
        await handle_play(call_connection_client, bienvenida)
        await asyncio.sleep(3)
        await iniciar_reconocimiento(call_connection_client, target_participant)
    except Exception as e:
        app.logger.error("Error en handle_reforma_conversacion: %s", str(e))

@app.route("/api/incomingCall", methods=["POST"])
async def incoming_call_handler():
    events = await request.json
    for event_dict in events:
        event = EventGridEvent.from_dict(event_dict)
        if event.event_type == SystemEventNames.EventGridSubscriptionValidationEventName:
            return {"validationResponse": event.data["validationCode"]}
        elif event.event_type == "Microsoft.Communication.IncomingCall":
            incoming_call_context = event.data["incomingCallContext"]
            caller_raw_id = event.data["from"]["rawId"]
            caller_number = caller_raw_id.replace("4:", "")
            call_guid = str(uuid.uuid4())
            call_guid_to_caller[call_guid] = caller_number
            callback_uri = f"{CALLBACK_EVENTS_URI}/{call_guid}?callerId={caller_number}"
            await answer_call(incoming_call_context, callback_uri)
            app.logger.info(f"✅ Llamada respondida correctamente de {caller_number}.")
    return Response(status=200)

@app.route('/api/callbacks/<contextId>', methods=['POST'])
async def callback_events_handler(contextId):
    raw_body = await request.get_data()
    app.logger.info("🔔 Callback recibido: %s", raw_body)
    events = await request.get_json()
    if not events:
        return Response("No content", status=204)

    for event_dict in events:
        try:
            event = CloudEvent.from_dict(event_dict)
            call_connection_id = event.data['callConnectionId']
            app.logger.info("Evento %s para llamada ID: %s", event.type, call_connection_id)

            call_connection_client = call_automation_client.get_call_connection(call_connection_id)
            caller_number = call_guid_to_caller.get(contextId, "+573000000000")
            app.logger.info("🔔 TELEFONO TARGET: %s", caller_number)
            target_participant = PhoneNumberIdentifier(caller_number)

            if event.type == "Microsoft.Communication.CallConnected":
                await handle_reforma_conversacion(call_connection_client, call_connection_id, target_participant)

            elif event.type == "Microsoft.Communication.RecognizeCompleted":
                speech_result = event.data.get("speechResult", {})
                user_input = speech_result.get("speech", "").strip()
                app.logger.info("🗣 Usuario dijo: %s", user_input)

                if check_exit_condition(user_input):
                    despedida = "Gracias por tu consulta. ¡Hasta pronto!"
                    await handle_play(call_connection_client, despedida)
                    await asyncio.sleep(4)
                    await call_connection_client.hang_up(is_for_everyone=True)
                    call_state.pop(contextId, None)
                    call_guid_to_caller.pop(contextId, None)
                    return Response(status=200)

                user_input = normalizar_acronimos(user_input)
                openai_client = OpenAIClient()
                respuesta = openai_client.generate_response(user_input)
                call_state[contextId]['last_response'] = respuesta
                app.logger.info("🤖 Respuesta: %s", respuesta)

                await handle_play(call_connection_client, respuesta)
                await asyncio.sleep(1)
                await iniciar_reconocimiento(call_connection_client, target_participant)

            elif event.type == "Microsoft.Communication.RecognizeFailed":
                app.logger.warning("Reconocimiento fallido: %s", event.data)
                await handle_play(call_connection_client, "Lo siento, no pude entenderte. ¿Puedes repetirlo?")
                await asyncio.sleep(1)
                await iniciar_reconocimiento(call_connection_client, target_participant)

            elif event.type in ["Microsoft.Communication.PlayCompleted", "Microsoft.Communication.PlayFailed"]:
                app.logger.info("Reproducción finalizada. Esperando siguiente acción.")

            elif event.type == "Microsoft.Communication.CallDisconnected":
                app.logger.info("📞 Llamada finalizada. Limpieza de estado de %s", contextId)
                call_state.pop(contextId, None)
                call_guid_to_caller.pop(contextId, None)
            

        except Exception as e:
            app.logger.error("❌ Error en callback: %s", str(e))

    return Response(status=200)

if __name__ == "__main__":
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', '8000')}"]
    asyncio.run(serve(app, config))
