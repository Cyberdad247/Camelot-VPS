#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
r"""Gemini Live Multimodal WebSocket Gateway"""

import asyncio, base64, json, logging, os, sys, websockets


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
LOG = logging.getLogger('GeminiLiveGateway')

GEMINI_LIVE_HOST = 'generativelanguage.googleapis.com'
GEMINI_LIVE_PATH = '/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent'
API_KEY = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY') or ''

DEFAULT_PORT = int(os.getenv('GEMINI_LIVE_PORT', 8765))

KNIGHT_VOICE_MAP = {
    'MERLIN_OMEGA': {'voice': 'Fenrir', 'instructions': 'You are Merlin Omega, Arch-Sorcerer and Deep Logic Architect of Camelot-OS. Speak with wisdom, authority, and concise technical mastery.'},
    'SIR_BORIS': {'voice': 'Charon', 'instructions': 'You are Sir Boris, Lead Architect of Camelot-OS. Direct, authoritative, focused on system stability and orchestration.'},
    'SIR_HEIMDALL': {'voice': 'Puck', 'instructions': 'You are Sir Heimdall, Guardian of the Bifrost Bridge. Vigilant, crisp, monitoring mesh telemetry and security gates.'},
    'LADY_LAKISHA': {'voice': 'Aoede', 'instructions': 'You are Lady Lakisha, Voice OS Sentinel. Elegant, rapid, luxury brutalist clarity.'}
}

class GeminiLiveRelay:
    def __init__(self, knight_id = 'MERLIN_OMEGA'):
        self.knight_id = knight_id
        self.knight_config = KNIGHT_VOICE_MAP.get(knight_id.upper(), KNIGHT_VOICE_MAP['MERLIN_OMEGA'])
        self.gemini_ws = None
        self.client_ws = None

    async def connect_gemini_live(self):
        if not API_KEY:
            LOG.warning('No direct GOOGLE_API_KEY set. Operating in mock/CLIProxy bridge mode.')
            return None
        uri = f'wss://{GEMINI_LIVE_HOST}{GEMINI_LIVE_PATH}?key={API_KEY}'
        LOG.info(f'Connecting to Gemini Live BidiStream for {self.knight_id}...')
        try:
            ws = await websockets.connect(uri)
            setup_msg = {
                'setup': {
                    'model': 'models/gemini-2.0-flash-exp',
                    'generationConfig': {
                        'responseModalities': ['AUDIO'],
                        'speechConfig': {
                            'voiceConfig': {
                                'prebuiltVoiceConfig': {
                                    'voiceName': self.knight_config['voice']
                                   }
                            }
                          }
                    },
                    'systemInstruction': {
                       'parts': [{'text': self.knight_config['instructions']}]
                    }
                }
            }
            await ws.send(json.dumps(setup_msg))
            setup_resp = await ws.recv()
            LOG.info(f'Gemini Live setup response received: {setup_resp[:100]}')
            return ws
        except Exception as e:
            LOG.error(f'Failed to connect to Gemini Live: {e}')
            return None

    async def handle_client(self, websocket):
        LOG.info(f'Client connected to Gemini Live Relay from {websocket.remote_address}')
        self.client_ws = websocket
        self.gemini_ws = await self.connect_gemini_live()

        async def from_client_to_gemini():
            try:
                async for message in websocket:
                    if isinstance(message, bytes):
                        if self.gemini_ws:
                            audio_payload = {
                                'realtimeInput': {
                                    'mediaChunks': [{
                                        'mimeType': 'audio/pcm;rate=16000',
                                        'data': base64.b64encode(message).decode('utf-8')
                                    }]
                                }
                            }
                            await self.gemini_ws.send(json.dumps(audio_payload))
                    elif isinstance(message, str):
                        data = json.loads(message)
                        if data.get('type') == 'ping':
                            await websocket.send(json.dumps({'type': 'pong', 'status': 'ONLINE'}))
            except Exception as e:
                LOG.error(f'Client stream error: {e}')

        async def from_gemini_to_client():
            if not self.gemini_ws:
                return
            try:
                async for message in self.gemini_ws:
                    resp = json.loads(message)
                    server_content = resp.get('serverContent', {})
                    model_turn = server_content.get('modelTurn', {})
                    for part in model_turn.get('parts', []):
                        if 'inlineData' in part:
                            audio_b64 = part['inlineData'].get('data')
                            if audio_b64 and self.client_ws:
                                audio_bytes = base64.b64decode(audio_b64)
                                await self.client_ws.send(audio_bytes)
            except Exception as e:
                LOG.error(f'Gemini stream error: {e}')

        await asyncio.gather(from_client_to_gemini(), from_gemini_to_client())


async def run_server(port = DEFAULT_PORT):
    relay = GeminiLiveRelay()
    server = await websockets.serve(relay.handle_client, '0.0.0.0', port)
    LOG.info(f'Gemini Live Multimodal Gateway active on ws://0.0.0.0:{port}')
    await server.wait_closed()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    try:
        asyncio.run(run_server(port))
    except KeyboardInterrupt:
        LOG.info('Server stopped.')
