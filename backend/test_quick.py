"""Quick API test without needing Troi installed"""
import requests
import json

BASE_URL = "http://localhost:8001"  # Changed from 8000

def test_root():
    """Test root endpoint"""
    print("Testing root endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status: {response.status_code}")
        
        # Check if it's actually our API
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if data.get("message") == "Tidaloader API":
            print("✓ Correct API responding")
        else:
            print("✗ Wrong service responding!")
        print()
    except Exception as e:
        print(f"✗ Error: {e}\n")
        raise

def test_search():
    """Test track search"""
    print("Testing track search...")
    try:
        response = requests.get(f"{BASE_URL}/api/search/tracks", params={"q": "Radiohead OK Computer"})
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data['items'])} tracks")
            if data['items']:
                track = data['items'][0]
                print(f"First result: {track['artist']} - {track['title']}")
                print(f"Track ID: {track['id']}")
        else:
            print(f"Error: {response.text}")
        print()
    except Exception as e:
        print(f"✗ Error: {e}\n")
        raise

def test_album_search():
    """Test album search"""
    print("Testing album search...")
    try:
        response = requests.get(f"{BASE_URL}/api/search/albums", params={"q": "OK Computer"})
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data['items'])} albums")
            if data['items']:
                album = data['items'][0]
                print(f"First result: {album.get('title')} by {album.get('artist', {}).get('name', 'Unknown')}")
        else:
            print(f"Error: {response.text}")
        print()
    except Exception as e:
        print(f"✗ Error: {e}\n")
        raise

if __name__ == "__main__":
    print("🧪 Testing Tidaloader API")
    print(f"Base URL: {BASE_URL}\n")
    print("="*50 + "\n")
    
    try:
        test_root()
        test_search()
        test_album_search()
        print("✓ All basic tests passed!")
    except requests.exceptions.ConnectionError:
        print("✗ ERROR: Could not connect to server")
        print("  Make sure the backend is running:")
        print("  cd backend && .\\start.ps1")
    except Exception as e:
        print(f"✗ ERROR: {e}")