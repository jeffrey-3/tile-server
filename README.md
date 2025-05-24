# Offline Map Tile Server for UAV Ground Control Station

This system provides a local tile server that pre-downloads and caches map tiles for offline usage in UAV (drone) ground control stations. It ensures map availability in remote areas without internet connectivity.

## Features

- **Tile Pre-Downloading**: Cache map tiles from ArcGIS World Imagery
- **Local HTTP Server**: Serve tiles offline via Flask
- **Progress Tracking**: Monitor download status via API
- **Folium Integration**: Visualize cached maps in browser
- **Multi-threaded Downloads**: Faster tile fetching