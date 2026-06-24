import requests
import base64
import json

def main():
    api_key = "MK_TEST_GC3B8XG2XX"
    secret_key = "A663NRZA544DDPEM7KDN7Z8HRV6YXD8S"
    contract_code = "5867418298"
    
    # 1. Login
    raw_creds = f"{api_key}:{secret_key}"
    encoded_creds = base64.b64encode(raw_creds.encode('utf-8')).decode('utf-8')
    login_url = "https://sandbox.monnify.com/api/v1/auth/login"
    login_resp = requests.post(login_url, headers={"Authorization": f"Basic {encoded_creds}"}, timeout=10)
    token = login_resp.json().get("responseBody", {}).get("accessToken")
    
    # 2. Init transaction
    init_url = "https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction"
    payload = {
        "amount": 900.0,
        "customerName": "Test Customer",
        "customerEmail": "test@customer.com",
        "paymentReference": "EP-PRQ-2026-00476-TEST-1",
        "paymentDescription": "Test Checkout Initialization",
        "currencyCode": "NGN",
        "contractCode": contract_code,
        "redirectUrl": "http://posnext.local:8000/api/method/edgepayv1.edgepay.services.api.payment_request_callback"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("Testing Init Transaction...")
    try:
        response = requests.post(init_url, json=payload, headers=headers, timeout=10)
        print("Status Code:", response.status_code)
        print("Body:", response.text)
    except Exception as e:
        print("Error during request:", str(e))

if __name__ == "__main__":
    main()
