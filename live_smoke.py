"""Explicit live smoke test. Requires SARVAM_API_KEY in .env; incurs API usage."""
import os
from pathlib import Path
from dotenv import dotenv_values
from sarvam_service import SarvamService, ServiceError, explanation

key = os.getenv('SARVAM_API_KEY') or dotenv_values(Path(__file__).with_name('.env')).get('SARVAM_API_KEY')
if not key:
    print('SKIPPED: no API key. No live Sarvam endpoints have been verified.')
    raise SystemExit(0)
try:
    service = SarvamService(key)
    result = service.analyze('Your bank account will be blocked in 2 hours. Update KYC at https://example.com/verify-bank.')
    print('PASS: live sarvam-105b structured analysis and evidence validation')
    english = explanation(result)
    translations = {}
    for code in ('hi-IN', 'ta-IN', 'te-IN'):
        translations[code] = service.translate(english, code)
        print('PASS: live translation', code)
    audio = service.speak(translations['hi-IN'], 'hi-IN')
    print('PASS: live Bulbul Hindi WAV generation:', len(audio), 'bytes')
except ServiceError as exc:
    print('FAILED:', str(exc))
    raise SystemExit(1)
