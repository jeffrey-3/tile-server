import os
import requests
import threading
import math
from PyQt5.QtCore import QObject, pyqtSignal

class TileDownloader(QObject):
    TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    TILE_FOLDER = "tiles"
    THREADS = 20
    EARTH_RADIUS = 6378137  # Earth's radius in meters (WGS84)

    progress_updated = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal()

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
                self.progress_updated.emit(self.completed, self.total_tiles)

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
        
        if not self._cancel:
            self.finished.emit()

downloader = TileDownloader()
downloader.download_all_tiles(43.859968, -79.416525, 1000, 1, 16)