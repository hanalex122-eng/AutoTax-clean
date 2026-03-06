import requests

# AutoTax API adresi
URL = "https://autotax-clean-production.up.railway.app"

# Swagger'dan aldığın access_token buraya
TOKEN = "BURAYA_TOKEN_YAPISTIR"

# Authorization header
headers = {
    "Authorization": f"Bearer {TOKEN}"
}

# Yüklemek istediğin dosya
files = {
    "file": open("yeni rechnung.jpeg", "rb")
}

print("📤 OCR gönderiliyor...")

response = requests.post(
    f"{URL}/api/ocr/upload",
    headers=headers,
    files=files
)

print("Status:", response.status_code)
print("Response:")
print(response.text)

TOKEN =  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlM2U2M2UxYS0xZTg3LTRmMjAtYTAyYi1mZTMwYWJhODdmODUiLCJlbWFpbCI6InRlc3RAYXV0b3RheC5jb20iLCJwbGFuIjoiZnJlZSIsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjE3NzI4MjI4MTh9.Sb6o65LI2i001NngvUHmgRktRrGUWe0yijJOd4xe6gc"