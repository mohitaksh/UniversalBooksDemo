"""
test_call.py
────────────
Quick manual test script to trigger an outbound call via the FastAPI server.
Run the server first:  uvicorn server:app --port 8000

Usage:
    python test_call.py
    python test_call.py --type institution
"""

import asyncio
import sys
import httpx


async def main():
    url = "http://127.0.0.1:8000/call"

    # Default: name-based call
    call_type = "name"
    name = "Santosh Kumar"

    # Check for --type flag
    if "--type" in sys.argv:
        idx = sys.argv.index("--type")
        if idx + 1 < len(sys.argv):
            call_type = sys.argv[idx + 1]

    if call_type == "institution":
        name = "Tiwari Tutorials"

    payload = {
        "phone_number": "+919999999999",
        "name": name,
        "call_type": call_type,
    }

    print(f"Calling {payload['phone_number']} as {call_type}: {name}")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.json()}")
    except httpx.ConnectError:
        print(f"Connection failed — is the server running at {url}?")
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
