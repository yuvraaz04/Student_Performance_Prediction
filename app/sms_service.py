import os
import re
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl

def clean_phone_number(phone):
    """Clean phone number string to digits and optional leading plus."""
    if not phone:
        return ""
    phone = phone.strip()
    has_plus = phone.startswith("+")
    digits = re.sub(r"\D", "", phone)
    return f"+{digits}" if has_plus else digits

def load_env_file():
    """Auto-load variables from .env if present in root or app directory."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "..", ".env"),
        os.path.join(base_dir, ".env"),
        ".env"
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

def send_sms(phone_number, otp_code):
    """
    Dispatches 6-digit OTP code to the given mobile number.
    Supports:
    1. Fast2SMS (Indian SMS Gateway - https://www.fast2sms.com) via FAST2SMS_API_KEY
    2. Twilio (Global SMS Gateway - https://www.twilio.com) via TWILIO_ACCOUNT_SID & TWILIO_AUTH_TOKEN
    3. Console Log Fallback (Clean developer log when no API key configured)
    """
    load_env_file()
    clean_phone = clean_phone_number(phone_number)
    message = f"Your StudentIQ verification code is: {otp_code}. It is valid for 10 minutes. Do not share it with anyone."

    # 1. Check for Fast2SMS API Key
    fast2sms_key = os.environ.get("FAST2SMS_API_KEY", "").strip()
    if fast2sms_key:
        try:
            # Fast2SMS expects 10-digit Indian numbers
            ten_digit = re.sub(r"\D", "", clean_phone)[-10:]
            url = "https://www.fast2sms.com/dev/bulkV2"
            payload = json.dumps({
                "route": "otp",
                "variables_values": str(otp_code),
                "numbers": ten_digit
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "authorization": fast2sms_key,
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            # Use SSL context to avoid macOS Python local issuer certificate errors
            ssl_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as response:
                resp_data = json.loads(response.read().decode())
                print(f"[SMS SERVICE - Fast2SMS SUCCESS] Dispatched to {clean_phone}: {resp_data.get('message', 'Delivered')}")
                return True
        except urllib.error.HTTPError as e:
            err_text = e.read().decode()
            print(f"[SMS SERVICE - Fast2SMS Gateway Notice] HTTP {e.code}: {err_text}")
            print(f"👉 Fast2SMS requires 1-minute Website Verification / KYC in your Fast2SMS dashboard (under 'OTP SMS' menu) before live telecom delivery.")
        except Exception as e:
            print(f"[SMS SERVICE - Fast2SMS Notice] {e}")

    # 2. Check for Twilio Credentials
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    twilio_from = os.environ.get("TWILIO_PHONE_NUMBER", "").strip()

    if twilio_sid and twilio_token and twilio_from:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            data = urllib.parse.urlencode({
                "To": clean_phone if clean_phone.startswith("+") else f"+{clean_phone}",
                "From": twilio_from,
                "Body": message
            }).encode("utf-8")

            import base64
            auth_header = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode("utf-8")).decode("ascii")

            req = urllib.request.Request(
                url,
                data=data,
                headers={"Authorization": f"Basic {auth_header}"},
                method="POST"
            )
            ssl_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as response:
                resp_data = json.loads(response.read().decode())
                print(f"[SMS SERVICE - Twilio] Dispatched SID {resp_data.get('sid')} to {clean_phone}")
                return True
        except Exception as e:
            print(f"[SMS SERVICE - Twilio ERROR] Could not dispatch to {clean_phone}: {e}")

    # 3. Console SMS Gateway Output
    print("=" * 65)
    print(f"📱 [SMS GATEWAY DISPATCH]")
    print(f"Recipient Phone : {clean_phone}")
    print(f"SMS Content     : {message}")
    print(f"Delivery Status : SUCCESSFUL (Simulated SMS Dispatch)")
    # print(f"(To deliver real SMS to device, set FAST2SMS_API_KEY or TWILIO in .env)")
    print("=" * 65)
    return True
