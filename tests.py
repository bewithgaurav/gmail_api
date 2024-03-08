import unittest
import os
import json
import sqlite3
from datetime import datetime
from script import authenticate_gmail, fetch_emails, store_emails, load_rules, apply_rules

class TestEmailProcessing(unittest.TestCase):

    def test_authentication(self):
        # Test authentication with Google OAuth
        credentials = authenticate_gmail()
        self.assertIsNotNone(credentials, "Authentication failed")

    def test_fetch_emails(self):
        # Test fetching emails from Gmail
        service, messages = fetch_emails()
        self.assertIsNotNone(service, "Gmail service object is None")
        self.assertGreater(len(messages), 0, "No emails fetched")

    def test_store_emails(self):
        # Test storing emails in SQLite database
        service, messages = fetch_emails()
        store_emails(service, messages)
        conn = sqlite3.connect('emails.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM emails")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertGreater(count, 0, "No emails stored in database")

    def test_load_rules(self):
        # Test loading rules from JSON file
        rules = load_rules('rules.json')
        self.assertIsNotNone(rules, "No rules loaded from JSON file")
        self.assertGreater(len(rules), 0, "No rules found in JSON file")

    def test_apply_rules(self):
        # Test applying rules to emails
        service, messages = fetch_emails()
        store_emails(service, messages)
        rules = load_rules('rules.json')
        apply_rules(service, rules)
        # Additional assertions can be added to verify the effects of rule application

if __name__ == '__main__':
    unittest.main()
