import os
from pathlib import Path
import streamlit as st
from dotenv import dotenv_values
from sarvam_service import (SarvamService, ServiceError, LANGUAGES,
                            VOICE_LANGUAGES, MAX_INPUT, explanation, validate_input)

st.set_page_config(page_title='ScamSuno | Understand Scams', page_icon='🛡️', layout='wide')
st.markdown('''<style>
.stApp {background: radial-gradient(ellipse at top left,#143345 0%,#080f20 55%);color:#edf4fc;}
.block-container {max-width:1380px;padding-top:2.2rem;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:18px;}
h1,h2,h3 {letter-spacing:-.035em;}
.stButton>button[kind="primary"] {background:#47e0bf;color:#07221c;border:0;font-weight:700;}
.stButton>button {border-radius:10px;}
[data-testid="stText"] {white-space:pre-wrap;overflow-wrap:anywhere;}
</style>''', unsafe_allow_html=True)

EXAMPLES = {
    'Bank KYC': 'Dear customer, your bank account will be blocked within 2 hours. Update your KYC immediately at https://example.com/verify-bank.',
    'UPI reward': 'Congratulations! You have won a ₹5000 cashback reward. To receive your money, first pay a ₹99 verification fee.',
    'Job offer': 'You have been selected for a work-from-home job earning ₹3000 daily. Send your Aadhaar details and registration payment today.',
}
for key, value in {'message': '', 'result': None, 'analyzed_message': '',
                   'translations': {}, 'audios': {}, 'translation_errors': {}}.items():
    if key not in st.session_state:
        st.session_state[key] = value

def load_example(name):
    st.session_state.message = EXAMPLES[name]

def clear_results():
    st.session_state.result = None
    st.session_state.analyzed_message = ''
    st.session_state.translations = {}
    st.session_state.audios = {}
    st.session_state.translation_errors = {}

with st.sidebar:
    st.header('Settings')
    env_key = os.getenv('SARVAM_API_KEY') or dotenv_values(Path(__file__).with_name('.env')).get('SARVAM_API_KEY', '')
    session_key = st.text_input('Sarvam API key', type='password', help='Used only in this browser session. Never added to source files.')
    api_key = session_key.strip() or (env_key or '').strip()
    if api_key:
        st.success('API key loaded • not yet validated')
    else:
        st.info('Add a Sarvam key here or set SARVAM_API_KEY in .env.')
    st.caption('Submitted messages are sent to Sarvam AI for analysis. Remove personal details, OTPs, PINs and passwords first.')
    st.button('Clear analysis & audio', on_click=clear_results)
    st.caption('23 explanation languages · 11 voice languages')

st.caption('DIGITAL SAFETY, IN YOUR LANGUAGE')
st.title('🛡️ ScamSuno')
st.subheader('AI-Powered Scam Awareness for Every Indian Language')
st.write('Paste a suspicious message. Understand the warning signs. Stay safe in your own language.')
st.caption('Understand Scams. Stay Safe. In Your Language.')
left, right = st.columns([1, 1.15], gap='large')
with left:
    with st.container(border=True):
        st.subheader('01 / Inspect a message')
        st.caption('Try a synthetic test case — these are invented examples.')
        cols = st.columns(3)
        for col, name in zip(cols, EXAMPLES):
            col.button(name, on_click=load_example, args=(name,), width='stretch')
        message = st.text_area('Suspicious message', key='message', height=220,
                               max_chars=MAX_INPUT, placeholder='Paste an SMS, WhatsApp message or payment request…')
        language_name = st.selectbox('Preferred explanation language', list(LANGUAGES), index=1)
        language = LANGUAGES[language_name]
        analyze = st.button('Analyze Message', type='primary', width='stretch')
        st.caption('No links are opened. No messages or payments are sent.')
        if analyze:
            try:
                text = validate_input(message)
                if text == st.session_state.analyzed_message and st.session_state.result:
                    st.info('Showing your existing assessment. No analysis call repeated.')
                else:
                    clear_results()
                    with st.spinner('Checking potential warning signs with Sarvam…'):
                        result = SarvamService(api_key).analyze(text)
                    st.session_state.result = result
                    st.session_state.analyzed_message = text
                    st.session_state.translations['en-IN'] = explanation(result)
            except ServiceError as exc:
                st.error(str(exc))

with right:
    with st.container(border=True):
        st.subheader('02 / Understand the warning signs')
        result = st.session_state.result
        if not result:
            st.info('Your assessment will appear here after analysis.')
            st.markdown('**Look for pressure, requests for secrets, and payments to claim rewards.**')
            st.caption('ScamSuno explains potential indicators and safe verification steps. It cannot prove a message is fraudulent.')
        else:
            stale = message.strip() != st.session_state.analyzed_message
            if stale:
                st.warning('The input has changed. This assessment belongs to the previous message; analyze the new message to update it.')
            with st.expander('Original analyzed message'):
                st.text(st.session_state.analyzed_message)
            risk = result['risk_level']
            color = {'High': '#ffb3b3', 'Medium': '#ffdb8a', 'Low': '#8fe5c3'}[risk]
            st.markdown(f'<div style="color:{color};font-size:1.5rem;font-weight:750">{risk} risk indicators</div>', unsafe_allow_html=True)
            st.caption('AI-generated assessment • not a calibrated probability or proof of fraud')
            st.text(result['summary'])
            with st.expander('Evidence & verification steps (English)', expanded=True):
                for i, flag in enumerate(result['red_flags'], 1):
                    st.caption(f'WARNING SIGN {i} · exact quote')
                    st.text(flag['evidence'])
                    st.text(flag['reason'])
                if not result['red_flags']:
                    st.text('No clear indicators identified. This does not guarantee safety.')
                st.markdown('**Recommended actions**')
                for i, action in enumerate(result['recommended_actions'], 1):
                    st.text(f'{i}. {action}')
            st.divider()
            st.subheader(f'Your explanation · {language_name}')
            errors = st.session_state.translation_errors
            translations = st.session_state.translations
            retry = False
            if language not in translations:
                retry = st.button('Retry translation' if language in errors else 'Translate explanation')
            if language not in translations and (language not in errors or retry):
                try:
                    with st.spinner(f'Translating into {language_name}…'):
                        translations[language] = SarvamService(api_key).translate(translations['en-IN'], language)
                    errors.pop(language, None)
                except ServiceError as exc:
                    errors[language] = str(exc)
            if language in errors:
                st.error(errors[language])
            if language in translations:
                st.text(translations[language])
                st.caption('Original evidence above stays unchanged. Translation may contain errors.')
                if language not in VOICE_LANGUAGES:
                    st.info('Bulbul voice is unavailable for this language. Your translated explanation is available above.')
                elif st.button('Listen to Explanation', disabled=stale):
                    if language not in st.session_state.audios:
                        try:
                            with st.spinner('Creating your voice explanation…'):
                                st.session_state.audios[language] = SarvamService(api_key).speak(translations[language], language)
                        except ServiceError as exc:
                            st.error(str(exc))
                if language in st.session_state.audios:
                    st.audio(st.session_state.audios[language], format='audio/wav')

st.divider()
st.caption('Powered by Sarvam-105B · Sarvam Translate v1 · Bulbul v3 | 22 Indian languages + English; voice in 10 Indian languages + English.')
st.caption('Awareness support only. Verify through official channels you find independently. A low-risk result does not guarantee safety.')
