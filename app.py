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
import threading
import os
import logging
import uuid
from urllib.parse import urlencode
from dotenv import load_dotenv
import asyncio
from collections import defaultdict
import os
from hypercorn.asyncio import serve
from hypercorn.config import Config
import asyncio
import html

call_guid_to_caller = defaultdict(lambda: "+573000000000")

app = Quart(__name__, template_folder="template")
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Configuraciones desde variables de entorno
ACS_CONNECTION_STRING = os.getenv("ACS_CONNECTION_STRING")
ACS_PHONE_NUMBER = os.getenv("ACS_PHONE_NUMBER")
TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER")
CALLBACK_URI_HOST = os.getenv("CALLBACK_URI_HOST")  # URL de ngrok
CALLBACK_EVENTS_URI = CALLBACK_URI_HOST + "/api/callbacks"
COGNITIVE_SERVICES_ENDPOINT = os.getenv("COGNITIVE_SERVICES_ENDPOINT")

SPEECH_TO_TEXT_VOICE = "es-US-PalomaNeural"

call_automation_client = CallAutomationClient.from_connection_string(ACS_CONNECTION_STRING)

# Utilidades

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

##INBOUND CALL
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

# async def handle_play(call_connection_client: CallConnectionClient, text_to_play: str):
#     play_source = TextSource(text=text_to_play, voice_name=SPEECH_TO_TEXT_VOICE)
#     await call_connection_client.play_media_to_all(play_source)

async def handle_play(call_connection_client, text_to_play: str):
    ssml_text = f"""
    <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
           xmlns:mstts="http://www.w3.org/2001/mstts"
           xml:lang="es-CO">
        <voice name="{SPEECH_TO_TEXT_VOICE}">
            <prosody rate="slow">{text_to_play}</prosody>
        </voice>
    </speak>
    """
    ssml_source = SsmlSource(ssml_text=ssml_text)
    await call_connection_client.play_media_to_all(ssml_source)

async def handle_reforma_conversacion(call_connection_client: CallConnectionClient, call_connection_id: str, target_participant: PhoneNumberIdentifier):
    try:
        bienvenida = "Hola, soy tu asistente virtual para resolver dudas sobre la reforma pensional en Colombia. ¿Qué deseas saber?"
        # play_source = TextSource(text=bienvenida, voice_name=SPEECH_TO_TEXT_VOICE)
        # await call_connection_client.play_media_to_all(play_source)
        await handle_play(call_connection_client, bienvenida)
        await asyncio.sleep(3)
        await iniciar_reconocimiento(call_connection_client, target_participant)
        #threading.Timer(3, iniciar_reconocimiento, args=[call_connection_client, target_participant]).start()
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
            caller_raw_id = event.data["from"]["rawId"]  # <-- IMPORTANTE
            caller_number = caller_raw_id.replace("4:", "")
            call_guid = str(uuid.uuid4())
            call_guid_to_caller[call_guid] = caller_number
            callback_uri = f"{CALLBACK_EVENTS_URI}/{call_guid}?callerId={caller_number}"
            await answer_call(incoming_call_context, callback_uri)
            app.logger.info(f"✅ Llamada respondida correctamente de {caller_number}.")
    return Response(status=200)

# @app.route("/api/incomingCall", methods=["POST"])
# async def incoming_call():
#     try:
#         print("📥 Recibiendo evento en /api/incomingCall...")
#         data = await request.get_json()
#         print("✅ Datos recibidos:", data)
#         return "", 200
#     except Exception as e:
#         print("❌ Error en /api/incomingCall:", str(e))
#         return "Error interno", 500


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
            #target_participant = PhoneNumberIdentifier(TARGET_PHONE_NUMBER)
            caller_number = call_guid_to_caller.get(contextId, "+573000000000")
            app.logger.info("🔔 TELEFONO TARGET: %s", caller_number)
            target_participant = PhoneNumberIdentifier(caller_number)
            #target_participant = PhoneNumberIdentifier(event.data.get("from", {}).get("phoneNumber", {}).get("value", "+573000000000"))

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
                    await iniciar_reconocimiento(call_connection_client, target_participant)
                    #threading.Timer(4, lambda: call_connection_client.hang_up(is_for_everyone=True)).start()
                    return Response(status=200)

                user_input = normalizar_acronimos(user_input)
                openai_client = OpenAIClient()
                respuesta = openai_client.generate_response(user_input)
                app.logger.info("🤖 Respuesta: %s", respuesta)

                await handle_play(call_connection_client, respuesta)
                #threading.Timer(1, iniciar_reconocimiento, args=[call_connection_client, target_participant]).start()
                await asyncio.sleep(1)
                await iniciar_reconocimiento(call_connection_client, target_participant)


            elif event.type == "Microsoft.Communication.RecognizeFailed":
                app.logger.warning("Reconocimiento fallido: %s", event.data)
                await handle_play(call_connection_client, "Lo siento, no pude entenderte. ¿Puedes repetirlo?")
                await asyncio.sleep(1)
                await iniciar_reconocimiento(call_connection_client, target_participant)
                #threading.Timer(1, iniciar_reconocimiento, args=[call_connection_client, target_participant]).start()

            elif event.type in ["Microsoft.Communication.PlayCompleted", "Microsoft.Communication.PlayFailed"]:
                app.logger.info("Reproducción finalizada. Esperando siguiente acción.")

        except Exception as e:
            app.logger.error("❌ Error en callback: %s", str(e))

    return Response(status=200)

# if __name__ == "__main__":
#     config = Config()
#     config.bind = [f"0.0.0.0:{os.environ.get('PORT', '8000')}"]
#     asyncio.run(serve(app, config))

if __name__ == '__main__':
    app.run(port=8000)