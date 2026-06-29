# Chargeback Analyst Tool

AI-assisted tool that takes a chargeback case and produces an analyst-ready representment workup.

---

## Quickstart (under 10 minutes from clone)

### 1. Clone the repo

```bash
git clone https://github.com/jallenjallen-dev/checkout_takehome_test
cd checkout_takehome_test
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Mac / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your OpenAI API key

> **You must add your own OpenAI API key before the tool will run.**
> The key needs access to `gpt-4o` (or any vision-capable model with structured output support).

```bash
cp .env.example .env
```

Then open `.env` and replace the placeholder:

```
OPENAI_API_KEY=sk-your-key-here
```

---

## Run the CLI

```bash
python cli.py --case CB-2025-0001
```

## Run the Streamlit UI

```bash
streamlit run app.py
```
