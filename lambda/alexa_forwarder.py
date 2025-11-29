"""
AWS Lambda Function - Alexa Skill Forwarder

This lightweight function translates Alexa's JSON format to our agent's simple API,
then formats the agent's response back for Alexa.

Deployment:
1. Create Lambda function in AWS Console
2. Copy this code into the function
3. Set AGENT_URL environment variable to your Cloudflare Tunnel URL
4. Configure Alexa Skill to use this Lambda ARN

Environment Variables:
- AGENT_URL: Your Cloudflare/ngrok tunnel URL (e.g., https://xxx.trycloudflare.com)
"""

import json
import os
import urllib.request
import urllib.error


def lambda_handler(event, context):
    """
    Main Lambda handler for Alexa Skill requests.

    Args:
        event: Alexa request JSON
        context: Lambda context object

    Returns:
        Alexa response JSON
    """

    # Get agent URL from environment variable
    agent_url = os.environ.get('AGENT_URL')
    if not agent_url:
        return build_alexa_response(
            "Configuration error. Please contact the developer.",
            should_end_session=True
        )

    # Ensure agent URL doesn't have trailing slash
    agent_url = agent_url.rstrip('/')

    # Log the request (viewable in CloudWatch)
    print(f"Received Alexa request: {json.dumps(event)}")

    # Extract request type
    request_type = event['request']['type']

    # Handle LaunchRequest (user says "Alexa, open home brain")
    if request_type == 'LaunchRequest':
        return build_alexa_response(
            "Welcome to your home automation system. What would you like me to do?",
            should_end_session=False
        )

    # Handle SessionEndedRequest
    if request_type == 'SessionEndedRequest':
        return build_alexa_response("", should_end_session=True)

    # Handle IntentRequest (user gives a command)
    if request_type == 'IntentRequest':
        intent_name = event['request']['intent']['name']

        # Handle built-in intents
        if intent_name == 'AMAZON.CancelIntent' or intent_name == 'AMAZON.StopIntent':
            return build_alexa_response("Goodbye!", should_end_session=True)

        if intent_name == 'AMAZON.HelpIntent':
            return build_alexa_response(
                "You can say things like: turn living room to fire, make bedroom cozy, or make it feel like I'm under the sea. What would you like?",
                should_end_session=False
            )

        # Handle fallback intent (when Alexa doesn't understand)
        # This happens when utterances don't match - we'll treat it as a command too
        if intent_name == 'AMAZON.FallbackIntent' or intent_name == 'CatchAllIntent':
            # Extract the query from slots
            slots = event['request']['intent'].get('slots', {})
            query_slot = slots.get('query', {})
            command = query_slot.get('value')

            if not command:
                return build_alexa_response(
                    "I didn't catch that. Please try again.",
                    should_end_session=False
                )

            # Forward to agent
            try:
                agent_response = call_agent(agent_url, command)
                return build_alexa_response(
                    agent_response,
                    should_end_session=True
                )
            except Exception as e:
                print(f"Error calling agent: {str(e)}")
                return build_alexa_response(
                    "Sorry, I had trouble communicating with the home automation system. Please try again.",
                    should_end_session=True
                )

    # Unknown request type
    return build_alexa_response(
        "I didn't understand that request.",
        should_end_session=True
    )


def call_agent(agent_url, command):
    """
    Call the local agent API via Cloudflare Tunnel.

    Args:
        agent_url: Base URL of agent (e.g., https://xxx.trycloudflare.com)
        command: Natural language command

    Returns:
        Agent's text response

    Raises:
        Exception: If API call fails
    """
    url = f"{agent_url}/api/command"

    # Build request
    data = json.dumps({'command': command}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )

    # Call agent
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response_data = json.loads(response.read().decode('utf-8'))

            if response_data.get('success'):
                return response_data.get('response', 'Done!')
            else:
                error = response_data.get('error', 'Unknown error')
                raise Exception(f"Agent returned error: {error}")

    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise Exception(f"Network error: {e.reason}")


def build_alexa_response(speech_text, should_end_session=True, reprompt_text=None):
    """
    Build a properly formatted Alexa response.

    Args:
        speech_text: What Alexa should say
        should_end_session: Whether to end the conversation
        reprompt_text: Optional text if user doesn't respond

    Returns:
        Alexa response JSON
    """
    response = {
        'version': '1.0',
        'response': {
            'outputSpeech': {
                'type': 'PlainText',
                'text': speech_text
            },
            'shouldEndSession': should_end_session
        }
    }

    # Add reprompt if continuing conversation
    if not should_end_session and reprompt_text:
        response['response']['reprompt'] = {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        }

    return response


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'request': {
            'type': 'IntentRequest',
            'intent': {
                'name': 'SmartHomeIntent',
                'slots': {
                    'command': {
                        'value': 'turn living room to fire'
                    }
                }
            }
        }
    }

    # Set test environment
    os.environ['AGENT_URL'] = 'https://activity-assists-retailer-newspaper.trycloudflare.com'

    # Test
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
