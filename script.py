import os
import json
import sqlite3
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# Define Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.modify']

# Function to authenticate Gmail API
def authenticate_gmail():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def reset_database(cursor):
    """Reset the database by deleting all records from the emails table."""
    cursor.execute("DELETE FROM emails")

# Function to fetch top 5 emails from Gmail Inbox
def fetch_emails():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=10).execute()
    messages = results.get('messages', [])
    for message in messages:
        print(message)
    return service, messages

# Function to store emails in the database
def store_emails(service, messages):
    conn = sqlite3.connect('emails.db')
    cursor = conn.cursor()
    reset_database(cursor)
    cursor.execute('''CREATE TABLE IF NOT EXISTS emails
                      (id TEXT PRIMARY KEY, subject TEXT, sender TEXT, date TIMESTAMP, snippet TEXT, unread INTEGER)''')
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        subject = next((header['value'] for header in msg['payload']['headers'] if header['name'] == 'Subject'), '')
        sender = next((header['value'] for header in msg['payload']['headers'] if header['name'] == 'From'), '')
        date = datetime.fromtimestamp(int(msg['internalDate']) / 1000)
        snippet = msg['snippet']
        unread = 'UNREAD' in msg['labelIds']
        print(subject, sender, date, snippet, unread)
        cursor.execute("INSERT INTO emails (id, subject, sender, date, snippet, unread) VALUES (?, ?, ?, ?, ?, ?)",
                       (message['id'], subject, sender, date, snippet, unread))
    conn.commit()
    conn.close()

# Function to load rules from JSON file
def load_rules(filename):
    with open(filename, 'r') as file:
        rules = json.load(file)
    return rules

# Function to apply rules to emails
def apply_rules(service, rules):
    conn = sqlite3.connect('emails.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emails")
    rows = cursor.fetchall()  # Fetch all rows from the database
    conn.close()

    for row in rows:
        email = {
            'id': row[0],
            'subject': row[1],
            'sender': row[2],
            'date': datetime.fromisoformat(row[3]),  # Convert ISO format string to datetime
            'snippet': row[4],
            'unread': bool(row[5])
        }

        for rule in rules:
            conditions = rule['conditions']
            predicate = rule['predicate']
            actions = rule['actions']
            matches = []

            for condition in conditions:
                field = condition['field']
                operator = condition['operator']
                value = condition['value']
                if field == 'sender':
                    field_value = email['sender']
                elif field == 'subject':
                    field_value = email['subject']
                elif field == 'received':
                    received_date = email['date']
                    if operator == 'less than':
                        if isinstance(value, int):  # Value is in days
                            delta = timedelta(days=value)
                        elif isinstance(value, str):  # Value is in months
                            delta = timedelta(days=30 * int(value))
                        else:
                            continue
                        if received_date > datetime.now() - delta:
                            matches.append(True)
                        else:
                            matches.append(False)
                        continue  # Skip further processing for 'Received' field
                    else:
                        continue  # Skip processing other operators for 'Received' field
                else:
                    continue  # Skip processing for unknown fields

                if operator == 'contains':
                    matches.append(value.lower() in field_value.lower())
                elif operator == 'does not contain':
                    matches.append(value.lower() not in field_value.lower())
                elif operator == 'equals':
                    matches.append(value.lower() == field_value.lower())
                elif operator == 'does not equal':
                    matches.append(value.lower() != field_value.lower())

            if predicate == 'all':
                if all(matches):
                    perform_actions(service, email['id'], actions)
            elif predicate == 'any':
                if any(matches):
                    perform_actions(service, email['id'], actions)


# Function to perform actions on emails
def perform_actions(service, email_id, actions):
    for action in actions:
        if action == 'mark as read':
            service.users().messages().modify(userId='me', id=email_id, body={'removeLabelIds': ['UNREAD']}).execute()
        elif action == 'mark as unread':
            service.users().messages().modify(userId='me', id=email_id, body={'addLabelIds': ['UNREAD']}).execute()
        elif action.startswith('move'):
            label_id = action.split(':')[1]
            service.users().messages().modify(userId='me', id=email_id, body={'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']}).execute()

if __name__ == '__main__':
    # Fetch emails
    service, messages = fetch_emails()
    # Store emails in the database
    store_emails(service, messages)
    # Load rules from JSON file
    rules = load_rules('rules.json')
    # Apply rules to emails
    apply_rules(service, rules)
