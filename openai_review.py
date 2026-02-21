import requests

url = "https://chatgpt.com/share/69937d30-249c-8000-ae3e-e9e0861b6073"

# Send HTTP GET request
response = requests.get(url)

# Check that the request succeeded
if response.status_code == 200:
    # Save the HTML to a file
    with open("page.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("HTML downloaded and saved as page.html")
else:
    print(f"Failed to download HTML, status code: {response.status_code}")