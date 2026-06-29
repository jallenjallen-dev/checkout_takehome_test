# Chargeback Analyst Tool

## Setup

```bash
git clone <your-repo-url>
cd <repo-folder>
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

## Run the CLI

```bash
python cli.py --case CB-2025-0001
```

## Run the Streamlit UI

```bash
streamlit run app.py
```
