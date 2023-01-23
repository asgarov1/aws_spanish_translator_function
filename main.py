import json
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from constants import VERIFY_TOKEN, GOOGLE_TRANSLATION_API_KEY, WHATSAPP_TOKEN

# Http Statuses
OK = 200
FORBIDDEN = 403
BAD_REQUEST = 400


def create_response(body, status_code=OK):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def handle_get(event):
    """
    https://developers.facebook.com/docs/graph-api/webhooks/getting-started#verification-requests
    to learn more about GET request for webhook verification
    :param event:
    :return:
    """
    query_parameters = event.get('queryStringParameters')
    if query_parameters is not None:
        hub_mode = query_parameters.get('hub.mode')
        if hub_mode == 'subscribe':
            return handle_subscribe_mode(query_parameters)
        else:
            return create_response('Error, wrong mode', FORBIDDEN)

    return create_response('Error, no query parameters', BAD_REQUEST)


def handle_subscribe_mode(query_parameters):
    verify_token = query_parameters.get('hub.verify_token')
    if verify_token == VERIFY_TOKEN:
        challenge = query_parameters.get('hub.challenge')
        return create_response(int(challenge))
    else:
        return create_response('Error, wrong validation token', FORBIDDEN)


def create_whatsapp_response_json(recipient, message_body):
    return {
        "messaging_product": "whatsapp",
        "to": recipient,
        "text": {"body": message_body},
    }


def send_reply(phone_number_id, whatsapp_token, message_from, reply_message):
    path = "https://graph.facebook.com/v12.0/"+phone_number_id+"/messages?access_token="+whatsapp_token
    message = create_whatsapp_response_json(message_from, reply_message)

    request = Request(path, urlencode(message).encode())
    json_response = urlopen(request).read().decode()
    print('Sent reply to whatsapp with the following response: ' + str(json_response))


def get_translation(word_to_translate, source='es', target='en'):
    """
    Typical response looks like (for example for 'donde')':
    {
      "data": {
        "translations": [
          {
            "translatedText": "where"
          }
        ]
      }
    }
    :param word_to_translate:
    :return:
    """
    translate_url = f'https://translation.googleapis.com/language/translate/v2?key={GOOGLE_TRANSLATION_API_KEY}' \
                    f'&source={source}&target={target}&q={word_to_translate}'
    response = json.loads(urlopen(translate_url).read())
    print('Translation received: ' + str(response))
    return response.get('data', {}).get('translations', {})[0].get('translatedText')


def handle_post(event):
    # body is a valid dict sent as string so we need to convert it to dict
    body = json.loads(event.get('body'))

    for entry in body.get('entry', {}):
        for change in entry.get('changes'):
            value = change.get('value', {})
            messages = value.get('messages')
            for message in messages:
                message_time = datetime.fromtimestamp(int(message.get('timestamp')))
                # only process messages of type text and received in last 3 seconds
                if message.get('type') == 'text' and message_time > datetime.utcnow() - timedelta(seconds=3):
                    phone_number_id = value.get('metadata', {}).get('phone_number_id')
                    message_from = message.get('from')
                    message_body = message.get('text').get('body')

                    translation = get_translation(message_body.replace(" ", "%20"))

                    send_reply(phone_number_id, WHATSAPP_TOKEN, message_from, translation)

                return create_response('Done')


######################
# Lambda Entry Point #
######################
def lambda_handler(event, context):
    http_method = event.get('requestContext', {}).get('http', {}).get('method')
    if http_method == 'GET':
        return handle_get(event)
    elif http_method == 'POST':
        return handle_post(event)
    else:
        return create_response('Unsupported method', BAD_REQUEST)
