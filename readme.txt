C:\Users\Bodruk\Documents\Python\CNX1>

C:\Users\Bodruk\AppData\Local\Programs\Python\Python311\python.exe -m venv venv

python3 -m venv venv

.\venv\Scripts\Activate
source venv/bin/activate

pip install -r requirements.txt
pip install "uvicorn[standard]"
uvicorn app.main:app --host 127.0.0.1 --port 8001


ngrok http 8000