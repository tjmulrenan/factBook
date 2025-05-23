from anthropic import Client
import os

client = Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=100,
    temperature=0.5,
    messages=[
        {"role": "user", "content": "Tell me a fun fact about space."}
    ]
)

print(response.content[0].text)