import requests
import json

# Test launching a workflow with a Gemini agent
url = "http://localhost:8000/api/enterprise/workflows/launch"

payload = {
    "name": "Gemini Agent Test Workflow",
    "steps": [
        {
            "agent": {
                "name": "GeminiAgent",
                "role": "ai-assistant",
                "tools": ["google-gemini"],
                "mcp_endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key=AIzaSyATZzImNH_QY7de0PlbGfQ4bVFkaUIHOmY",
                "context": {"prompt": "Summarize the latest AI research trends in 2025."}
            },
            "task": "Summarize AI research trends for 2025"
        }
    ]
}

headers = {"Content-Type": "application/json"}

response = requests.post(url, data=json.dumps(payload), headers=headers)
print("Status Code:", response.status_code)
print("Response:", response.json())
