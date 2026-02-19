import requests
import json
import uuid

# Backend URL (from start_server.bash: 7728)
BASE_URL = "https://127.0.0.1:7728"

# Test data
test_email = f"test_{uuid.uuid4().hex[:6]}@example.com"
test_password = "testpassword123"

def test_auth():
    print(f"Testing signup for {test_email}...")
    try:
        # Signup
        signup_res = requests.post(
            f"{BASE_URL}/signup",
            json={"email": test_email, "password": test_password},
            verify=False
        )
        print(f"Signup Status: {signup_res.status_code}")
        if signup_res.status_code != 200:
            print(f"Signup Error: {signup_res.text}")
            return False

        print("Testing login...")
        # Login (OAuth2PasswordRequestForm expects form data)
        login_res = requests.post(
            f"{BASE_URL}/login",
            data={"username": test_email, "password": test_password},
            verify=False
        )
        print(f"Login Status: {login_res.status_code}")
        if login_res.status_code != 200:
            print(f"Login Error: {login_res.text}")
            return False

        token_data = login_res.json()
        if "access_token" in token_data:
            print("Login successful! Token received.")
            return True
        else:
            print(f"Unexpected login response: {token_data}")
            return False

    except Exception as e:
        print(f"Error during test: {e}")
        return False

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    success = test_auth()
    if not success:
        exit(1)
