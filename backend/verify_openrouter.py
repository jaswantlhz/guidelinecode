
import os
from dotenv import load_dotenv
import requests

# Load env variables
env_path = "../agent/.env"
load_dotenv(env_path)

api_key = os.getenv("OPENROUTER_API_KEY")

print(f"Checking OpenRouter API with key: {api_key[:10]}...")

try:
    response = requests.get(
        "https://openrouter.ai/api/v1/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "CPIC RAG Debugger"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        models = data.get("data", [])
        print(f"Success! Found {len(models)} models.")
        
        # Check specifically for free ones we want to use
        targets = [
            "meta-llama/llama-3.2-3b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
            "mistralai/mistral-7b-instruct:free",
            "google/gemini-2.0-pro-exp-02-05:free"
        ]
        
        print("\nChecking specific free models:")
        for t in targets:
            found = any(m["id"] == t for m in models)
            # requests to check pricing is complex, just check existence of ID
            # In /models response, pricing is usually included.
            
            # Let's find the model object
            model_obj = next((m for m in models if m["id"] == t), None)
            if model_obj:
                print(f"[OK] {t} is listed. details: {model_obj.get('pricing')}")
            else:
                print(f"[MISSING] {t} is NOT in the list of available models.")
                
        # List ANY model with 'free' in ID
        print("\nAll 'free' models found:")
        free_models = [m["id"] for m in models if ":free" in m["id"] or "free" in m["id"]]
        for fm in free_models[:10]: # Print first 10
            print(f"- {fm}")
            
    else:
        print(f"Error: {response.status_code} - {response.text}")

except Exception as e:
    print(f"Exception: {e}")
