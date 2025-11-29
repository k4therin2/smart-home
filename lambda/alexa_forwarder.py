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

    # Log the COMPLETE request (viewable in CloudWatch)
    print("="*80)
    print("FULL ALEXA REQUEST:")
    print(json.dumps(event, indent=2))
    print("="*80)
    print(f"Agent URL configured: {agent_url}")

    # Send full event to server debug endpoint for inspection
    print("Sending full event to server debug endpoint...")
    send_debug_to_server(agent_url, event)

    # Extract request type with error handling
    try:
        request_type = event['request']['type']
        print(f"Request type: {request_type}")
    except KeyError as e:
        print(f"ERROR: Missing key in event structure: {e}")
        print(f"Event keys: {list(event.keys())}")
        print(f"Request keys: {list(event.get('request', {}).keys())}")
        return build_alexa_response(
            "I had trouble understanding that request.",
            should_end_session=True
        )

    # Handle LaunchRequest (user says "Alexa, open home brain")
    if request_type == 'LaunchRequest':
        print("Handling LaunchRequest")
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
        print(f"Intent name: {intent_name}")

        # Handle built-in intents
        if intent_name == 'AMAZON.CancelIntent' or intent_name == 'AMAZON.StopIntent':
            print("Handling Cancel/Stop intent")
            return build_alexa_response("Goodbye!", should_end_session=True)

        if intent_name == 'AMAZON.HelpIntent':
            print("Handling Help intent")
            return build_alexa_response(
                "You can say things like: turn living room to fire, make bedroom cozy, or make it feel like I'm under the sea. What would you like?",
                should_end_session=False
            )

        # Handle fallback intent (when Alexa doesn't understand)
        # This happens when utterances don't match - we'll treat it as a command too
        if intent_name == 'AMAZON.FallbackIntent' or intent_name == 'CatchAllIntent':
            print(f"Handling CatchAllIntent/FallbackIntent")

            # Extract the query from slots with defensive parsing
            try:
                slots = event['request']['intent'].get('slots', {})
                print(f"All slots: {json.dumps(slots, indent=2)}")

                # Try to get the query slot
                query_slot = slots.get('query', {})
                print(f"Query slot contents: {json.dumps(query_slot, indent=2)}")

                # Extract command value
                command = query_slot.get('value')
                print(f"Extracted command value: '{command}'")

                # Also check if there are any other slots
                if not command:
                    print("Checking all slots for any value...")
                    for slot_name, slot_data in slots.items():
                        print(f"  Slot '{slot_name}': {slot_data}")
                        if isinstance(slot_data, dict) and slot_data.get('value'):
                            command = slot_data.get('value')
                            print(f"  Found value in slot '{slot_name}': {command}")
                            break

            except Exception as e:
                print(f"ERROR extracting slots: {str(e)}")
                print(f"Intent structure: {json.dumps(event['request'].get('intent', {}), indent=2)}")
                command = None

            if not command:
                print("WARNING: No command found in any slots!")
                return build_alexa_response(
                    "I didn't catch that. Please try again.",
                    should_end_session=False
                )

            # Forward to agent
            print(f"Calling agent with command: {command}")
            try:
                agent_response = call_agent(agent_url, command)
                print(f"Agent responded: {agent_response}")
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

        # Unknown intent
        print(f"Unknown intent: {intent_name}")
        return build_alexa_response(
            "I didn't understand that command.",
            should_end_session=True
        )

    # Unknown request type
    return build_alexa_response(
        "I didn't understand that request.",
        should_end_session=True
    )


def send_debug_to_server(agent_url, event):
    """
    Send the entire Alexa event to the server's debug endpoint.
    Useful for troubleshooting JSON structure issues.
    """
    url = f"{agent_url}/debug/raw"
    print(f"Sending debug data to: {url}")

    try:
        data = json.dumps(event).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            print(f"Debug endpoint response: {response_data}")
            return True
    except Exception as e:
        print(f"Failed to send debug data: {str(e)}")
        return False


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
    print(f"Calling URL: {url}")

    # Build request
    data = json.dumps({'command': command}).encode('utf-8')
    print(f"Request data: {data.decode('utf-8')}")

    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )

    # Call agent
    try:
        print("Sending HTTP request...")
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"Response status: {response.status}")
            response_text = response.read().decode('utf-8')
            print(f"Response body: {response_text}")
            response_data = json.loads(response_text)

            if response_data.get('success'):
                return response_data.get('response', 'Done!')
            else:
                error = response_data.get('error', 'Unknown error')
                raise Exception(f"Agent returned error: {error}")

    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.reason}")
        raise Exception(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        print(f"URLError: {e.reason}")
        raise Exception(f"Network error: {e.reason}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise


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
