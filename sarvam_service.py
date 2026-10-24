import base64
import io
import json
import re
import wave
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError
from prompts import SCHEMA, SYSTEM_PROMPT

LANGUAGES = {
    'English': 'en-IN', 'Hindi': 'hi-IN', 'Tamil': 'ta-IN',
    'Telugu': 'te-IN', 'Bengali': 'bn-IN', 'Marathi': 'mr-IN',
    'Gujarati': 'gu-IN', 'Kannada': 'kn-IN', 'Malayalam': 'ml-IN',
    'Punjabi': 'pa-IN', 'Odia': 'od-IN', 'Assamese': 'as-IN',
    'Urdu': 'ur-IN', 'Nepali': 'ne-IN', 'Bodo': 'brx-IN',
    'Dogri': 'doi-IN', 'Konkani': 'kok-IN', 'Kashmiri': 'ks-IN',
    'Maithili': 'mai-IN', 'Manipuri': 'mni-IN', 'Sanskrit': 'sa-IN',
    'Santali': 'sat-IN', 'Sindhi': 'sd-IN',
}
VOICE_LANGUAGES = set(list(LANGUAGES.values())[:11])
MAX_INPUT = 4000

class ServiceError(Exception):
    pass

def validate_input(message):
    if not isinstance(message, str) or not message.strip():
        raise ServiceError('Paste a message before analyzing.')
    if len(message) > MAX_INPUT:
        raise ServiceError(f'Keep the message within {MAX_INPUT} characters.')
    return message.strip()

def parse_analysis(raw, message):
    if not isinstance(raw, str) or len(raw) > 16000:
        raise ValueError('Missing or oversized response')
    raw = raw.strip()
    if raw.startswith('```json') and raw.endswith('```'):
        raw = raw[7:-3].strip()
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != set(SCHEMA['required']):
        raise ValueError('Invalid fields')
    def valid_text(value, limit):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= limit
    if data['risk_level'] not in ('Low', 'Medium', 'High'):
        raise ValueError('Invalid risk')
    if not valid_text(data['summary'], 350):
        raise ValueError('Invalid summary')
    flags = data['red_flags']
    if not isinstance(flags, list) or len(flags) > 4:
        raise ValueError('Invalid flags')
    for flag in flags:
        if not isinstance(flag, dict) or set(flag) != {'evidence', 'reason'}:
            raise ValueError('Invalid flag')
        if not valid_text(flag['evidence'], MAX_INPUT) or flag['evidence'] not in message:
            raise ValueError('Evidence is not verbatim')
        if not valid_text(flag['reason'], 250):
            raise ValueError('Invalid reason')
    actions = data['recommended_actions']
    if not isinstance(actions, list) or not 1 <= len(actions) <= 4:
        raise ValueError('Invalid actions')
    if not all(valid_text(a, 250) for a in actions):
        raise ValueError('Invalid action')
    return data

def explanation(data):
    return '\n\n'.join([
        'AI assessment, not proof of fraud. Risk level: ' + data['risk_level'] + '.',
        data['summary'],
        'Warning signs: ' + ' '.join(f['reason'] for f in data['red_flags']),
        'Safe next steps: ' + ' '.join(data['recommended_actions']),
        'Verify the sender independently. Even a low-risk assessment does not guarantee safety.',
    ])

def chunks(text, limit):
    while len(text) > limit:
        cut = text.rfind(' ', 0, limit + 1)
        if cut < limit // 2:
            cut = limit
        yield text[:cut]
        text = text[cut:].lstrip()
    if text:
        yield text

class SarvamService:
    def __init__(self, api_key):
        if not api_key or not api_key.strip():
            raise ServiceError('Add your Sarvam API key in Settings or .env.')
        self.client = SarvamAI(api_subscription_key=api_key.strip(), timeout=45)

    def _call(self, method, **kwargs):
        try:
            return method(**kwargs, request_options={'max_retries': 0})
        except ApiError as exc:
            if exc.status_code in (401, 403):
                raise ServiceError('Sarvam rejected the API key. Check the key and account access.') from None
            if exc.status_code == 429:
                raise ServiceError('Sarvam rate limit reached. Wait briefly, then retry.') from None
            if exc.status_code in (400, 422):
                raise ServiceError('Sarvam rejected this request. Check model access and input, then retry.') from None
            raise ServiceError('Sarvam is temporarily unavailable. Please retry.') from None
        except Exception:
            raise ServiceError('Could not reach Sarvam or the request timed out. Check your connection and retry.') from None

    def analyze(self, message):
        message = validate_input(message)
        for attempt in range(2):
            response = self._call(self.client.chat.completions, model='sarvam-105b',
                messages=[{'role': 'system', 'content': SYSTEM_PROMPT + (
                    '\nPrevious output was invalid. Follow all limits and quote exact evidence.' if attempt else '')},
                    {'role': 'user', 'content': json.dumps({'untrusted_message': message}, ensure_ascii=False)}],
                reasoning_effort=None, max_tokens=1600, temperature=0.1,
                response_format={'type': 'json_schema', 'json_schema': {
                    'name': 'scam_awareness', 'strict': True, 'schema': SCHEMA}})
            try:
                if response.choices[0].finish_reason == 'length':
                    raise ValueError('Truncated')
                return parse_analysis(response.choices[0].message.content, message)
            except (ValueError, TypeError, AttributeError, IndexError):
                pass
        raise ServiceError('Sarvam returned an invalid assessment twice. Please try again.')

    def translate(self, text, language):
        if language not in LANGUAGES.values():
            raise ServiceError('Unsupported translation language.')
        if language == 'en-IN':
            return text
        # Evidence stays separate. Protect identifiers unexpectedly repeated in prose.
        protected = {}
        def mask(match):
            token = f'ZXQ{len(protected)}QXZ'
            protected[token] = match.group()
            return token
        masked = re.sub(r'https?://\S+|www\.\S+|[₹$€£]?\d[\d,.+\-]*', mask, text)
        translated = []
        for part in chunks(masked, 1800):
            response = self._call(self.client.text.translate, input=part,
                source_language_code='en-IN', target_language_code=language,
                model='sarvam-translate:v1', mode='formal')
            if not isinstance(response.translated_text, str) or not response.translated_text.strip():
                raise ServiceError('Sarvam returned an empty translation. Retry translation.')
            translated.append(response.translated_text)
        result = '\n\n'.join(translated)
        for token, original in protected.items():
            if result.count(token) != 1:
                raise ServiceError('Translation changed a protected identifier. Original evidence is preserved; retry translation.')
            result = result.replace(token, original)
        return result

    def speak(self, text, language):
        if language not in VOICE_LANGUAGES:
            raise ServiceError('Voice is unavailable for this language; translation remains available.')
        frames, params = [], None
        for part in chunks(text, 2400):
            response = self._call(self.client.text_to_speech.convert,
                text=part, language_code=language, model='bulbul:v3', speaker='shubh',
                output_audio_codec='wav', speech_sample_rate=22050)
            try:
                if not response.audios:
                    raise ValueError('No audio')
                for encoded in response.audios:
                    with wave.open(io.BytesIO(base64.b64decode(encoded, validate=True)), 'rb') as audio:
                        current = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
                        if params and params != current:
                            raise ValueError('Incompatible audio')
                        params = current
                        frames.append(audio.readframes(audio.getnframes()))
            except (ValueError, wave.Error, EOFError, AttributeError):
                raise ServiceError('Sarvam returned invalid WAV audio. Please retry voice generation.') from None
        if not params or not any(frames):
            raise ServiceError('Sarvam returned empty audio.')
        output = io.BytesIO()
        with wave.open(output, 'wb') as audio:
            audio.setnchannels(params[0])
            audio.setsampwidth(params[1])
            audio.setframerate(params[2])
            audio.writeframes(b''.join(frames))
        return output.getvalue()
