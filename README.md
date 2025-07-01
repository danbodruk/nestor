# Nestor

This project uses FastAPI and a PostgreSQL database.

## Setup

1. Create a Python virtual environment:
   ```bash
   # Windows
   python -m venv venv

   # Unix/macOS
   python3 -m venv venv
   ```
2. Activate the virtual environment:
   ```bash
   # Windows
   venv\Scripts\activate

   # Unix/macOS
   source venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   pip install "uvicorn[standard]"
   ```

## Environment variables

Create a `.env` file in the project root with the following variables:

```env
POSTGRES_HOST=your_host
POSTGRES_PORT=5431
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_database
```

## Running the application

Start the server using Uvicorn:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

You can expose the local development server via `ngrok` if needed:

```bash
ngrok http 8000
```
