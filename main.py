from fastapi import FastAPI
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
import os
from urllib.parse import urlencode
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "YOUR_CLIENT_ID.apps.googleusercontent.com")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/auth/callback"

SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid"
]

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return HTMLResponse(open("static/index.html").read())

@app.get("/auth/login")
async def login():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }
    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(google_auth_url)

@app.get("/auth/callback")
async def auth_callback(code: str):
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    token_response = requests.post(token_url, data=token_data)
    tokens = token_response.json()
    access_token = tokens.get("access_token")

    creds = Credentials(token=access_token)
    service = build("gmail", "v1", credentials=creds)

    results = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=5).execute()
    messages = results.get("messages", [])

    email_list_html = "<h1>Latest Emails</h1><ul>"
    for message in messages:
        msg = service.users().messages().get(userId="me", id=message["id"], format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])

        # Extract headers
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(No Subject)")
        sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "(Unknown Sender)")
        recipient = next((h["value"] for h in headers if h["name"].lower() == "to"), "(Unknown Recipient)")

        # Extract body content
        body = ""
        if "parts" in msg["payload"]:
            # multipart email - try to get the plain text part
            for part in msg["payload"]["parts"]:
                if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                    break
        else:
            # single part email
            if "data" in msg["payload"]["body"]:
                body = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode("utf-8", errors="ignore")

        email_list_html += f"""
            <li>
                <strong>From:</strong> {sender}<br>
                <strong>To:</strong> {recipient}<br>
                <strong>Subject:</strong> {subject}<br>
                <strong>Body:</strong> <pre>{body}</pre>
            </li>
            <hr>
        """

    email_list_html += "</ul>"


    return HTMLResponse(email_list_html)
