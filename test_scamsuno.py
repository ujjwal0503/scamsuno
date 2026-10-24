import base64
import copy
import io
import json
import unittest
import wave
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from sarvam_service import SarvamService, ServiceError, parse_analysis, validate_input, chunks

MESSAGE = 'Your account will be blocked. Pay a fee now.'
RESULT = {'risk_level': 'High', 'summary': 'The message pressures you to pay.',
          'red_flags': [{'evidence': 'Pay a fee now', 'reason': 'An unexpected fee is requested.'}],
          'recommended_actions': ['Verify through the official bank app.']}
def completion(value):
    return NS(choices=[NS(message=NS(content=value), finish_reason='stop')])

class ServiceTests(unittest.TestCase):
    def test_parse_valid_unicode_and_fences(self):
        self.assertEqual(parse_analysis(json.dumps(RESULT), MESSAGE), RESULT)
        self.assertEqual(parse_analysis('```json\n' + json.dumps(RESULT) + '\n```', MESSAGE), RESULT)
        value = copy.deepcopy(RESULT)
        value['red_flags'][0]['evidence'] = 'खाता बंद'
        self.assertEqual(parse_analysis(json.dumps(value), 'आपका खाता बंद होगा'), value)

    def test_reject_invalid_schema_and_fabricated_evidence(self):
        for update in [{'risk_level': '97%'}, {'summary': ''}, {'recommended_actions': []},
                       {'red_flags': [{'evidence': 'invented', 'reason': 'Bad'}]}, {'extra': 1}]:
            value = dict(RESULT, **update)
            with self.assertRaises(ValueError):
                parse_analysis(json.dumps(value), MESSAGE)
        for raw in ['```json\nnot json\n```', 'null', '[]', None]:
            with self.assertRaises(ValueError):
                parse_analysis(raw, MESSAGE)

    def test_input_and_key(self):
        for value in ['', '  ', 'a' * 4001]:
            with self.assertRaises(ServiceError):
                validate_input(value)
        with self.assertRaises(ServiceError):
            SarvamService('')
        self.assertTrue(SarvamService('test-only-not-a-real-key').client)

    def test_single_controlled_retry(self):
        service = SarvamService('test-key')
        service._call = Mock(side_effect=[completion('{}'), completion(json.dumps(RESULT))])
        self.assertEqual(service.analyze(MESSAGE), RESULT)
        self.assertEqual(service._call.call_count, 2)
        service._call = Mock(return_value=completion('{}'))
        with self.assertRaises(ServiceError):
            service.analyze(MESSAGE)
        self.assertEqual(service._call.call_count, 2)

    def test_translation_contract_and_identifiers(self):
        service = SarvamService('test-key')
        service._call = Mock(return_value=NS(translated_text='संदेश की जाँच करें।'))
        self.assertTrue(service.translate('Check the message.', 'hi-IN'))
        self.assertEqual(service._call.call_args.kwargs['model'], 'sarvam-translate:v1')
        service._call = Mock(return_value=NS(translated_text='changed identifier'))
        with self.assertRaises(ServiceError):
            service.translate('The fee is ₹99.', 'ta-IN')

    def test_audio_decode_and_unsupported_language(self):
        raw = io.BytesIO()
        with wave.open(raw, 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(22050)
            audio.writeframes(b'\x00\x00' * 100)
        service = SarvamService('test-key')
        service._call = Mock(return_value=NS(audios=[base64.b64encode(raw.getvalue()).decode()]))
        self.assertTrue(service.speak('Test.', 'hi-IN').startswith(b'RIFF'))
        with self.assertRaises(ServiceError):
            service.speak('Test.', 'ur-IN')
        service._call = Mock(return_value=NS(audios=['invalid']))
        with self.assertRaises(ServiceError):
            service.speak('Test.', 'hi-IN')

    def test_safe_api_errors(self):
        from sarvamai.core.api_error import ApiError
        service = SarvamService('test-key')
        for code, expected in [(403, 'API key'), (429, 'rate limit'), (500, 'unavailable')]:
            method = Mock(side_effect=ApiError(status_code=code, body='secret-payload'))
            with self.assertRaises(ServiceError) as caught:
                service._call(method)
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn('secret-payload', str(caught.exception))
        with self.assertRaises(ServiceError):
            service._call(Mock(side_effect=TimeoutError('secret')))

    def test_chunks(self):
        self.assertTrue(all(len(part) <= 1800 for part in chunks('क' * 5000, 1800)))

class UITests(unittest.TestCase):
    def test_examples_empty_missing_key(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file('app.py').run()
        self.assertFalse(app.exception)
        next(b for b in app.button if b.label == 'Analyze Message').click().run()
        self.assertIn('Paste a message', app.error[0].value)
        next(b for b in app.button if b.label == 'Bank KYC').click().run()
        self.assertIn('blocked within 2 hours', app.text_area[0].value)
        next(b for b in app.button if b.label == 'Analyze Message').click().run()
        self.assertIn('API key', app.error[0].value)
        self.assertFalse(app.exception)

    def test_reruns_language_changes_and_audio_cache(self):
        from streamlit.testing.v1 import AppTest
        with patch('sarvam_service.SarvamService') as factory:
            service = factory.return_value
            service.analyze.return_value = RESULT
            service.translate.return_value = 'संदेश की जाँच करें।'
            service.speak.return_value = b'RIFFmockaudio'
            app = AppTest.from_file('app.py').run()
            next(b for b in app.button if b.label == 'Bank KYC').click().run()
            next(b for b in app.button if b.label == 'Analyze Message').click().run()
            self.assertFalse(app.exception)
            app.run()
            self.assertEqual(service.analyze.call_count, 1)
            self.assertEqual(service.translate.call_count, 1)
            next(b for b in app.button if b.label == 'Analyze Message').click().run()
            self.assertEqual(service.analyze.call_count, 1)
            app.selectbox[0].select('Tamil').run()
            self.assertEqual(service.analyze.call_count, 1)
            self.assertEqual(service.translate.call_count, 2)
            for _ in range(2):
                next(b for b in app.button if b.label == 'Listen to Explanation').click().run()
            self.assertEqual(service.speak.call_count, 1)
            self.assertFalse(app.exception)

if __name__ == '__main__':
    unittest.main(verbosity=2)
