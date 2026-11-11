# SPDX-License-Identifier: MIT
import json, os, urllib.request, urllib.error, logging, argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
LOG = logging.getLogger('ExcaliburVoiceGateway')

S26_TAILSCALE_IP = os.getenv('S26_TAILSCALE_IP', '100.106.246.126')
S26_AUDIO_PORT = int(os.getenv('S26_AUDIO_PORT', 8092))
VPS_HUB_IP = os.getenv('VPS_HUB_IP', '162.35.107.134')

def trigger_voice_capture(duration=5, save_path=None):
    url = f'http://{S26_TAILSCALE_IP}:{S26_AUDIO_PORT}/capture'
    payload = json.dumps({'duration': duration}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    LOG.info(f'Autonomous trigger: capturing {duration}s from Excalibur (S26 Ultra)...')
    try:
        with urllib.request.urlopen(req, timeout=duration + 5) as resp:
            audio_bytes = resp.read()
            if save_path:
                Path(save_path).write_bytes(audio_bytes)
                LOG.info(f'Audio saved to {save_path}')
            return audio_bytes
    except Exception as e:
        LOG.error(f'Voice capture failed: {e}')
        return b''

def send_voice_response(text, knight='MERLIN_OMEGA'):
    url = f'http://{S26_TAILSCALE_IP}:{S26_AUDIO_PORT}/speak'
    payload = json.dumps({'text': text, 'speaker': knight}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    LOG.info(f'Sending {knight} vocal response to Excalibur speaker...')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        LOG.error(f'Failed to deliver voice response to S26 Ultra: {e}')
        return False

def check_excalibur_status():
    url = f'http://{S26_TAILSCALE_IP}:{S26_AUDIO_PORT}/status'
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {'status': 'OFFLINE', 'error': str(e)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Excalibur Autonomous Voice Gateway')
    parser.add_argument('--capture', type=int, help='Capture N seconds of voice from S26 Ultra')
    parser.add_argument('--speak', type=str, help='Speak message through S26 Ultra speaker')
    parser.add_argument('--knight', type=str, default='MERLIN_OMEGA', help='Knight speaker profile')
    parser.add_argument('--status', action='store_true', help='Check Excalibur voice node status')
    args = parser.parse_args()

    if args.status:
        print(json.dumps(check_excalibur_status(), indent=2))
    elif args.capture:
        raw = trigger_voice_capture(args.capture, 's26_voice_in.m4a')
        print(f'Captured {len(raw)} bytes of audio.')
    elif args.speak:
        ok = send_voice_response(args.speak, args.knight)
        print('Vocal transmission successful:', ok)
    else:
        print('Excalibur Voice Gateway Online.')
