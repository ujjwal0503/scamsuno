# ScamSuno
Understand Scams. Stay Safe. In Your Language.

A Streamlit hackathon prototype that uses Sarvam AI to explain potential scam
indicators in suspicious messages. It is an awareness assistant, not a fraud verdict.

## Run in VS Code
Open this folder. The selected interpreter is `.venv/Scripts/python.exe`.
In the terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For a fresh installation (Python 3.11+):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Add `SARVAM_API_KEY=your_key` to `.env`, or enter the key in the app's password field.
Get a key at https://dashboard.sarvam.ai/admin. Do not commit `.env` or share keys.
The app binds only to localhost. Do not expose a development server publicly.

## Models and features
- `sarvam-105b`: JSON-schema structured analysis, followed by local schema checks
  and exact-substring evidence validation. At most one retry for malformed output.
- `sarvam-translate:v1`: explanation translation; English is the internal language.
- `bulbul:v3`: `shubh` speaker, explicit WAV output, base64 decode and WAV validation.
- Session-only translation/audio cache. Buttons do not repeat analysis on reruns.
- Three labeled synthetic examples, navy/teal responsive layout, plain-text evidence.
- Empty/oversized-input validation, missing-key handling, timeouts and rate-limit errors.
- Evidence remains verbatim and separate from translation. Unexpected identifiers in
  prose are protected; a changed identifier causes a visible translation failure.

## Languages
Translation: English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada,
Malayalam, Punjabi, Odia, Assamese, Urdu, Nepali, Bodo, Dogri, Konkani, Kashmiri,
Maithili, Manipuri, Sanskrit, Santali and Sindhi.
Voice: English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada,
Malayalam, Punjabi and Odia. Other languages keep translation without voice.
These are documented endpoint capabilities, not a claim of live validation of every language.

## Checks
```powershell
.\.venv\Scripts\python.exe -m compileall -q app.py sarvam_service.py prompts.py test_scamsuno.py
.\.venv\Scripts\python.exe -m unittest -v test_scamsuno
```
Unit/UI tests use clearly isolated mocks; the running app never uses simulated AI.
Real API verification requires an account key with model access and credits.

## 60-second demonstration
0–15 seconds: “Millions of Indians receive suspicious digital messages, but language
barriers can make scam warnings harder to understand. ScamSuno uses Sarvam AI to
explain potential warning signs in the user's own language.”
15–30 seconds: Select the synthetic Bank KYC example and Hindi. Click Analyze Message.
Point out the exact evidence, risk label and independent verification steps.
30–45 seconds: Switch to Tamil. Explain that the existing analysis is reused and
Sarvam Translate supplies the local-language explanation. Click Listen to Explanation.
45–60 seconds: “Sarvam's voice technology makes the advice accessible through audio.
This is not proof of fraud: it is explainable digital-safety guidance. Our prototype
shows how multilingual AI can improve access to safety information.”
Allow for network latency; pre-generate the demonstration languages before presenting.

## Limitations and privacy
No OCR or voice input; these optional features were intentionally excluded.
AI and translations can be wrong. Low risk never guarantees safety. This app does
not verify domains/senders, fetch submitted links, contact banks, send SMS, or pay.
Messages go to Sarvam; remove private data and secrets before submission. Results
are held in the Streamlit session, not a database. Clear them using Settings.
A missing or rejected key blocks actual analysis; there is no fake fallback.

## Official references checked during implementation
- https://docs.sarvam.ai/api/api-guides-tutorials/chat-completion/overview
- https://docs.sarvam.ai/api-reference/text/translate-text
- https://docs.sarvam.ai/api-reference/text-to-speech/convert
- https://docs.sarvam.ai/api-reference/metaprompt
