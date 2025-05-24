import requests
import folium
import time

# Server configuration
SERVER_URL = "http://localhost:5000"

def preload_tiles(lat, lon, size_meters, min_zoom, max_zoom):
    """Trigger tile preloading on the server"""
    response = requests.post(
        f"{SERVER_URL}/preload",
        json={
            "lat": lat,
            "lon": lon,
            "size": size_meters,
            "min_zoom": min_zoom,
            "max_zoom": max_zoom
        }
    )
    return response.json()

def check_status():
    """Check download progress"""
    response = requests.get(f"{SERVER_URL}/status")
    return response.json()

def cancel_download():
    """Cancel current download"""
    response = requests.post(f"{SERVER_URL}/cancel")
    return response.json()

def create_folium_map(center, zoom_start):
    """Create a Folium map that uses our local tiles"""
    m = folium.Map(location=center, zoom_start=zoom_start, tiles=None)
    
    # Add our local tile layer using the standard TileLayer
    folium.TileLayer(
        tiles=f"{SERVER_URL}/tiles/{{z}}/{{x}}/{{y}}.png",
        attr="Local Tile Cache",
        name="Local Tiles",
        min_zoom=0,
        max_zoom=22,
        show=True
    ).add_to(m)
    
    # Add a default OpenStreetMap layer for comparison
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        attr='OpenStreetMap contributors'
    ).add_to(m)
    
    # Add a layer control
    folium.LayerControl().add_to(m)
    
    return m

def main():
    # Example coordinates (New York City)
    center_lat = 40.7128
    center_lon = -74.0060
    size_meters = 5000  # 5km area around center point
    min_zoom = 10
    max_zoom = 15
    
    # Start preloading tiles
    print("Starting tile preload...")
    preload_response = preload_tiles(center_lat, center_lon, size_meters, min_zoom, max_zoom)
    print(preload_response)
    
    # Monitor progress
    while True:
        status = check_status()
        print(f"Progress: {status['completed']}/{status['total']}")
        
        if not status['is_active'] or status['completed'] >= status['total']:
            break
            
        time.sleep(1)
    
    print("Tile download complete!")
    
    # Create and display the map
    print("Creating Folium map...")
    m = create_folium_map((center_lat, center_lon), min_zoom)
    m.save("example/local_tiles_map.html")
    print("Map saved to local_tiles_map.html - open this file in your browser")

if __name__ == "__main__":
    main()