import os
import requests
import threading
import math
from flask import Flask, send_from_directory, abort, jsonify, request
import os
from threading import Thread

class TileDownloader:
    TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    TILE_FOLDER = "tiles"
    THREADS = 20
    EARTH_RADIUS = 6378137  # Earth's radius in meters (WGS84)

    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.progress_lock = threading.Lock()
        self.completed = 0
        self.total_tiles = 0
        self._cancel = False

    @staticmethod
    def lat_lon_to_tile(lat, lon, zoom):
        """Convert latitude, longitude, and zoom level to tile coordinates."""
        lat_rad = math.radians(lat)
        n = 2 ** zoom
        tile_x = n * (lon + 180) / 360
        tile_y = n * (1 - (math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi)) / 2
        return tile_x, tile_y

    def calculate_bounding_box(self, center_lat, center_lon, size_meters):
        """
        Calculate bounding box coordinates from center point and size in meters.
        Returns (top_left, bottom_right) as ((lat, lon), (lat, lon))
        """
        # Calculate the angular distance in radians for the given size
        d_lat = size_meters / self.EARTH_RADIUS
        d_lon = size_meters / (self.EARTH_RADIUS * math.cos(math.radians(center_lat)))
        
        # Convert to degrees
        d_lat_deg = math.degrees(d_lat)
        d_lon_deg = math.degrees(d_lon)
        
        top_left = (center_lat + d_lat_deg/2, center_lon - d_lon_deg/2)
        bottom_right = (center_lat - d_lat_deg/2, center_lon + d_lon_deg/2)
        
        return top_left, bottom_right

    def download_tile(self, z, x, y):
        """Download a single tile and save it."""
        tile_path = os.path.join(self.TILE_FOLDER, str(z), str(x), f"{y}.png")
        
        if os.path.exists(tile_path):  # Skip if already downloaded
            return
        
        os.makedirs(os.path.dirname(tile_path), exist_ok=True)
        
        url = self.TILE_URL.format(z=z, x=x, y=y)
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(tile_path, "wb") as f:
                    f.write(response.content)
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {url}: {e}")

    def worker(self, tasks):
        """Worker thread to process download tasks."""
        while True:
            with self.lock:
                if not tasks or self._cancel:
                    break
                z, x, y = tasks.pop()
            
            if self._cancel:
                break
                
            self.download_tile(z, x, y)
            
            with self.progress_lock:
                self.completed += 1

    def calculate_total_tiles(self, min_zoom, max_zoom, center_lat, center_lon, size_meters):
        """Calculate total number of tiles that will be downloaded."""
        total = 0
        for zoom_level in range(min_zoom, max_zoom + 1):
            top_left, bottom_right = self.calculate_bounding_box(center_lat, center_lon, size_meters)
            top_left_tile = self.lat_lon_to_tile(top_left[0], top_left[1], zoom_level)
            bottom_right_tile = self.lat_lon_to_tile(bottom_right[0], bottom_right[1], zoom_level)
            
            x_count = math.ceil(bottom_right_tile[0]) - math.floor(top_left_tile[0])
            y_count = math.ceil(bottom_right_tile[1]) - math.floor(top_left_tile[1])
            total += x_count * y_count
        return total

    def cancel(self):
        """Cancel the download process."""
        self._cancel = True

    def download_all_tiles(self, center_lat, center_lon, size_meters, min_zoom, max_zoom):
        """Download tiles for all specified zoom levels using center coordinates and size."""
        self._cancel = False
        self.completed = 0
        self.total_tiles = self.calculate_total_tiles(min_zoom, max_zoom, center_lat, center_lon, size_meters)
        
        # Create all tasks
        all_tasks = []
        for zoom_level in range(min_zoom, max_zoom + 1):
            top_left, bottom_right = self.calculate_bounding_box(center_lat, center_lon, size_meters)
            top_left_tile = self.lat_lon_to_tile(top_left[0], top_left[1], zoom_level)
            bottom_right_tile = self.lat_lon_to_tile(bottom_right[0], bottom_right[1], zoom_level)
            
            x_range = range(math.floor(top_left_tile[0]), math.ceil(bottom_right_tile[0]))
            y_range = range(math.floor(top_left_tile[1]), math.ceil(bottom_right_tile[1]))
            
            all_tasks.extend([(zoom_level, x, y) for x in x_range for y in y_range])
        
        # Start workers
        threads = [threading.Thread(target=self.worker, args=(all_tasks,)) for _ in range(self.THREADS)]
        
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    
    def get_tile_path(self, z, x, y):
        """Get the filesystem path for a tile"""
        return os.path.join(self.TILE_FOLDER, str(z), str(x), f"{y}.png")

    def tile_exists(self, z, x, y):
        """Check if a tile exists locally"""
        return os.path.exists(self.get_tile_path(z, x, y))

    def get_available_zoom_levels(self):
        """Get list of zoom levels that have downloaded tiles"""
        zoom_path = os.path.join(self.TILE_FOLDER)
        if not os.path.exists(zoom_path):
            return []
        
        return [int(z) for z in os.listdir(zoom_path) if z.isdigit()]

    def get_tile_bounds(self, zoom):
        """Get the min/max x,y coordinates for a given zoom level"""
        zoom_path = os.path.join(self.TILE_FOLDER, str(zoom))
        if not os.path.exists(zoom_path):
            return None
        
        x_folders = [int(x) for x in os.listdir(zoom_path) if x.isdigit()]
        if not x_folders:
            return None
        
        min_x = min(x_folders)
        max_x = max(x_folders)
        
        y_values = []
        for x in x_folders:
            x_path = os.path.join(zoom_path, str(x))
            y_files = [int(y.split('.')[0]) for y in os.listdir(x_path) if y.endswith('.png')]
            y_values.extend(y_files)
        
        if not y_values:
            return None
        
        return {
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min(y_values),
            'max_y': max(y_values)
    }

app = Flask(__name__)

# Initialize your tile downloader
downloader = TileDownloader()

@app.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def serve_tile(z, x, y):
    tile_path = os.path.join(downloader.TILE_FOLDER, str(z), str(x), f"{y}.png")
    
    if not os.path.exists(tile_path):
        # Option 1: Return 404 if tile doesn't exist
        abort(404)
        
        # Option 2: Download the tile on demand (slower but more complete)
        # downloader.download_tile(z, x, y)
        # if not os.path.exists(tile_path):
        #     abort(404)
    
    return send_from_directory(os.path.dirname(tile_path), f"{y}.png")

@app.route('/preload', methods=['POST'])
def preload_tiles():
    """Endpoint to trigger tile preloading"""
    data = request.json
    thread = Thread(target=downloader.download_all_tiles,
                   kwargs={
                       'center_lat': data['lat'],
                       'center_lon': data['lon'],
                       'size_meters': data['size'],
                       'min_zoom': data['min_zoom'],
                       'max_zoom': data['max_zoom']
                   })
    thread.start()
    return jsonify({"status": "preloading started"})

@app.route('/status')
def get_status():
    """Get download progress status"""
    return jsonify({
        "completed": downloader.completed,
        "total": downloader.total_tiles,
        "is_active": not downloader._cancel
    })

@app.route('/cancel', methods=['POST'])
def cancel_download():
    """Cancel current download operation"""
    downloader.cancel()
    return jsonify({"status": "cancellation requested"})

@app.route('/metadata')
def get_metadata():
    """Get metadata about available tiles"""
    zoom_levels = downloader.get_available_zoom_levels()
    metadata = {
        "zoom_levels": zoom_levels,
        "bounds_per_zoom": {}
    }
    
    for z in zoom_levels:
        bounds = downloader.get_tile_bounds(z)
        if bounds:
            metadata["bounds_per_zoom"][z] = bounds
    
    return jsonify(metadata)

@app.route('/tilejson.json')
def get_tilejson():
    """Return a TileJSON document for this tileset"""
    return jsonify({
        "tilejson": "2.2.0",
        "name": "Local Tile Cache",
        "description": "Tiles downloaded from " + downloader.TILE_URL,
        "version": "1.0.0",
        "attribution": "Tile data © OpenStreetMap contributors",
        "scheme": "xyz",
        "tiles": [
            f"http://localhost:5000/tiles/{{z}}/{{x}}/{{y}}.png"
        ],
        "minzoom": min(downloader.get_available_zoom_levels() or [0]),
        "maxzoom": max(downloader.get_available_zoom_levels() or [0]),
        "bounds": [-180, -85, 180, 85]  # Default bounds
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)