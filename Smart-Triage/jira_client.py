import requests

BASE_URL = "http://localhost:8080/mock/api"  

def extract_description(data: dict) -> str:
    """
    Extract plain text from Jira's description (ADF format).
    """
    try:
        desc_obj = data["fields"]["description"]
        if desc_obj and "content" in desc_obj:
            # Navigate down into first paragraph → first content → text
            return desc_obj["content"][0]["content"][0]["text"]
        return "No description text found"
    except Exception:
        return "No description available"

def get_ticket_details(ticket_id: str):
    """
    Fetch Jira ticket details and extract description
    """
    try:
        response = requests.get(f"{BASE_URL}/{ticket_id}")
        if response.status_code == 200:
            data = response.json()
            description = extract_description(data)
            return {
                "id": data.get("id"),
                "key": data.get("key"),
                "summary": data["fields"].get("summary"),
                "description": description
            }
        else:
            return {"error": f"Failed with status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}
