# from azure.eventgrid import EventGridEvent, SystemEventNames
# from flask import Flask, Response, request, json, send_file, render_template, redirect
# from logging import INFO
# from azure.communication.callautomation import (
#     CallAutomationClient,
#     CallConnectionClient,
#     PhoneNumberIdentifier,
#     RecognizeInputType,
#     MicrosoftTeamsUserIdentifier,
#     CallInvite,
#     RecognitionChoice,
#     DtmfTone,
#     TextSource)
# from azure.core.messaging import CloudEvent

# # Your ACS resource connection string
# ACS_CONNECTION_STRING = "endpoint=https://botinfo.unitedstates.communication.azure.com/;accesskey=1guTFl7aIVgWq2tkZM4oSHEpLrL3owX2NHVr87eeefBe0p4TEC0eJQQJ99AKACULyCpETjDrAAAAAZCSEYQW"

# # Your ACS resource phone number will act as source number to start outbound call
# ACS_PHONE_NUMBER = "+18772123179"

# # Target phone number you want to receive the call.
# TARGET_PHONE_NUMBER = "+573002290279"

# # Callback events URI to handle callback events.
# CALLBACK_URI_HOST = "https://ac66-2800-e2-be80-b2b-e8de-bf37-37f6-c2d0.ngrok-free.app"
# CALLBACK_EVENTS_URI = CALLBACK_URI_HOST + "/api/callbacks"
# COGNITIVE_SERVICES_ENDPOINT = "https://cognitiveiabot.cognitiveservices.azure.com/"

# #(OPTIONAL) Your target Microsoft Teams user Id ex. "ab01bc12-d457-4995-a27b-c405ecfe4870"
# TARGET_TEAMS_USER_ID = "<TARGET_TEAMS_USER_ID>"

# TEMPLATE_FILES_PATH = "template"

# # Prompts for text to speech
# SPEECH_TO_TEXT_VOICE = "es-CO-SalomeNeural"
# MAIN_MENU = "Hola, te habla el Banco Contoso. Te llamamos para confirmar tu cita de mañana a las 9 de la mañana para abrir una nueva cuenta. Por favor, di confirmar si ese horario te sirve, o di cancelar si deseas cancelar la cita."
# CONFIRMED_TEXT = "Gracias por confirmar tu cita para mañana a las 9 de la mañana. Te esperamos."
# CANCEL_TEXT = "Tu cita ha sido cancelada. Si deseas reprogramarla, comunícate con el banco."
# CUSTOMER_QUERY_TIMEOUT = "Lo siento, no recibí respuesta. Por favor, intenta nuevamente."
# NO_RESPONSE = "No recibimos una respuesta. Vamos a confirmar tu cita automáticamente. ¡Hasta pronto!"
# INVALID_AUDIO = "Perdón, no entendí tu respuesta. Por favor, intenta de nuevo."

# # Etiquetas en español
# CONFIRM_CHOICE_LABEL = "Confirmar"
# CANCEL_CHOICE_LABEL = "Cancelar"
# RETRY_CONTEXT = "reintentar"

# call_automation_client = CallAutomationClient.from_connection_string(ACS_CONNECTION_STRING)

# app = Flask(__name__,
#             template_folder=TEMPLATE_FILES_PATH)

# def get_choices():
#     choices = [
#         RecognitionChoice(label=CONFIRM_CHOICE_LABEL, phrases=["Confirmar", "Uno", "Sí"], tone=DtmfTone.ONE),
#         RecognitionChoice(label=CANCEL_CHOICE_LABEL, phrases=["Cancelar", "Dos", "No"], tone=DtmfTone.TWO)
#     ]
#     return choices

# def get_media_recognize_choice_options(call_connection_client: CallConnectionClient, text_to_play: str, target_participant:str, choices: any, context: str):
#      play_source =  TextSource (text= text_to_play, voice_name= SPEECH_TO_TEXT_VOICE)
#      call_connection_client.start_recognizing_media(
#                 input_type=RecognizeInputType.CHOICES,
#                 target_participant=target_participant,
#                 choices=choices,
#                 play_prompt=play_source,
#                 interrupt_prompt=False,
#                 initial_silence_timeout=10,
#                 operation_context=context,
#                 speech_language="es-CO"  
#             )
     
# def handle_play(call_connection_client: CallConnectionClient, text_to_play: str):
#         play_source = TextSource(text=text_to_play, voice_name=SPEECH_TO_TEXT_VOICE) 
#         call_connection_client.play_media_to_all(play_source)

# # GET endpoint to place phone call
# @app.route('/outboundCall')
# def outbound_call_handler():
#     target_participant = PhoneNumberIdentifier(TARGET_PHONE_NUMBER)
#     source_caller = PhoneNumberIdentifier(ACS_PHONE_NUMBER)
#     call_connection_properties = call_automation_client.create_call(target_participant, 
#                                                                     CALLBACK_EVENTS_URI,
#                                                                     cognitive_services_endpoint=COGNITIVE_SERVICES_ENDPOINT,
#                                                                     source_caller_id_number=source_caller)
#     app.logger.info("Created call with connection id: %s", call_connection_properties.call_connection_id)
#     return redirect("/")


# # POST endpoint to handle callback events
# @app.route('/api/callbacks', methods=['POST'])
# def callback_events_handler():
#     app.logger.info("🔔 Callback recibido con body: %s", request.data)

#     if not request.json:
#         app.logger.warning("⚠️ No se recibió JSON válido.")
#         return Response("No content", status=204)

#     for event_dict in request.json:
#         try:
#             # Parsing callback events
#             event = CloudEvent.from_dict(event_dict)
#             call_connection_id = event.data['callConnectionId']
#             app.logger.info("%s event received for call connection id: %s", event.type, call_connection_id)

#             call_connection_client = call_automation_client.get_call_connection(call_connection_id)
#             target_participant = PhoneNumberIdentifier(TARGET_PHONE_NUMBER)

#             if event.type == "Microsoft.Communication.CallConnected":
#                 app.logger.info("Starting recognize")
#                 get_media_recognize_choice_options(
#                     call_connection_client=call_connection_client,
#                     text_to_play=MAIN_MENU,
#                     target_participant=target_participant,
#                     choices=get_choices(),
#                     context=""
#                 )

#             elif event.type == "Microsoft.Communication.RecognizeCompleted":
#                 app.logger.info("Recognize completed: data=%s", event.data)
#                 if event.data['recognitionType'] == "choices":
#                     label_detected = event.data['choiceResult']['label']
#                     phraseDetected = event.data['choiceResult']['recognizedPhrase']
#                     app.logger.info("Recognition completed, labelDetected=%s, phraseDetected=%s, context=%s", label_detected, phraseDetected, event.data.get('operationContext'))
#                     if label_detected == CONFIRM_CHOICE_LABEL:
#                         text_to_play = CONFIRMED_TEXT
#                     else:
#                         text_to_play = CANCEL_TEXT
#                     handle_play(call_connection_client=call_connection_client, text_to_play=text_to_play)

#             elif event.type == "Microsoft.Communication.RecognizeFailed":
#                 failedContext = event.data['operationContext']
#                 if failedContext == RETRY_CONTEXT:
#                     handle_play(call_connection_client=call_connection_client, text_to_play=NO_RESPONSE)
#                 else:
#                     resultInformation = event.data['resultInformation']
#                     app.logger.info("Encountered error during recognize, message=%s, code=%s, subCode=%s",
#                                     resultInformation['message'],
#                                     resultInformation['code'],
#                                     resultInformation['subCode'])
#                     if resultInformation['subCode'] in [8510]:
#                         textToPlay = CUSTOMER_QUERY_TIMEOUT
#                     else:
#                         textToPlay = INVALID_AUDIO

#                     get_media_recognize_choice_options(
#                         call_connection_client=call_connection_client,
#                         text_to_play=textToPlay,
#                         target_participant=target_participant,
#                         choices=get_choices(),
#                         context=RETRY_CONTEXT
#                     )

#             elif event.type in ["Microsoft.Communication.PlayCompleted", "Microsoft.Communication.PlayFailed"]:
#                 app.logger.info("Terminating call")
#                 call_connection_client.hang_up(is_for_everyone=True)

#         except Exception as e:
#             app.logger.error("❌ Error procesando el evento: %s", str(e))

#     # ✅ Este return está afuera del for — siempre devuelve una respuesta
#     return Response(status=200)


# # GET endpoint to render the menus
# @app.route('/')
# def index_handler():
#     return render_template("index.html")


# if __name__ == '__main__':
#     app.logger.setLevel(INFO)
#     app.run(port=8080)

from quart import Quart, request, Response
from azure.communication.callautomation.aio import CallAutomationClient
from azure.communication.callautomation import (
    CallConnectionClient,
    PhoneNumberIdentifier,
    RecognizeInputType,
    TextSource
)
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
        initial_silence_timeout=3,
        end_silence_timeout=2,
        speech_language="es-CO",
        operation_context="reforma_loop"
    )

async def handle_play(call_connection_client: CallConnectionClient, text_to_play: str):
    play_source = TextSource(text=text_to_play, voice_name=SPEECH_TO_TEXT_VOICE)
    await call_connection_client.play_media_to_all(play_source)

async def handle_reforma_conversacion(call_connection_client: CallConnectionClient, call_connection_id: str, target_participant: PhoneNumberIdentifier):
    try:
        bienvenida = "Hola, soy tu asistente virtual para resolver dudas sobre la reforma pensional en Colombia. ¿Qué deseas saber?"
        play_source = TextSource(text=bienvenida, voice_name=SPEECH_TO_TEXT_VOICE)
        await call_connection_client.play_media_to_all(play_source)
        await asyncio.sleep(3)
        await iniciar_reconocimiento(call_connection_client, target_participant)
        #threading.Timer(3, iniciar_reconocimiento, args=[call_connection_client, target_participant]).start()
    except Exception as e:
        app.logger.error("Error en handle_reforma_conversacion: %s", str(e))

# @app.route('/')
# def index_handler():
#     return render_template("index.html")


# @app.route('/outboundCall')
# def outbound_call_handler():
#     numero_usuario = request.args.get("numero")
#     if not numero_usuario:
#         return "Número no proporcionado", 400

#     target_participant = PhoneNumberIdentifier(numero_usuario)
#     source_caller = PhoneNumberIdentifier(ACS_PHONE_NUMBER)

#     call_connection_properties = call_automation_client.create_call(
#         target_participant,
#         CALLBACK_EVENTS_URI,
#         cognitive_services_endpoint=COGNITIVE_SERVICES_ENDPOINT,
#         source_caller_id_number=source_caller
#     )
#     app.logger.info("Llamada creada con ID: %s", call_connection_properties.call_connection_id)
#     return redirect("/")

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

if __name__ == '__main__':
    app.run(port=8080)
