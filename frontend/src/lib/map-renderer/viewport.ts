export class MapViewport {
  private position: { x: number; y: number } = { x: 0, y: 0 };
  private zoom: number = 1.0;
  private mapSize: { width: number; height: number };
  private canvasSize: { width: number; height: number };
  
  constructor(mapSize: { width: number; height: number }) {
    this.mapSize = mapSize;
    this.canvasSize = { width: 1920, height: 1080 };
  }

  // Resize canvas and optionally fit map to screen
  resize(width: number, height: number) {
    this.canvasSize = { width, height };
  }

  // Fit map height to screen (initial view)
  fitToScreen() {
    // Calculate zoom so map height fits canvas height
    this.zoom = this.canvasSize.height / this.mapSize.height;
    // Start at top-left corner (neutral position)
    this.position = { x: 0, y: 0 };
  }
  
  // Pan: move viewport
  pan(deltaX: number, deltaY: number) {
    this.position.x += deltaX / this.zoom;
    this.position.y += deltaY / this.zoom;
    
    // Wrap X (infinite horizontal scroll)
    this.position.x = ((this.position.x % this.mapSize.width) + this.mapSize.width) % this.mapSize.width;
    
    // Clamp Y (no vertical wrap)
    const viewHeight = this.canvasSize.height / this.zoom;
    this.position.y = Math.max(0, Math.min(this.position.y, this.mapSize.height - viewHeight));
    console.log(this.position.x);
    console.log(this.position.y);

  }
  
  // Zoom at cursor position
  zoomAt(cursorX: number, cursorY: number, zoomDelta: number) {
    // World point under cursor before zoom
    const worldX = this.position.x + cursorX / this.zoom;
    const worldY = this.position.y + cursorY / this.zoom;
    
    // Apply zoom
    this.zoom *= zoomDelta;
    this.zoom = Math.max(0.25, Math.min(this.zoom, 4));
    
    // Reposition so same world point is under cursor
    this.position.x = worldX - cursorX / this.zoom;
    this.position.y = worldY - cursorY / this.zoom;
    
    // Re-apply bounds
    this.position.x = ((this.position.x % this.mapSize.width) + this.mapSize.width) % this.mapSize.width;
    const viewHeight = this.canvasSize.height / this.zoom;
    this.position.y = Math.max(0, Math.min(this.position.y, this.mapSize.height - viewHeight));
  }
  
  // Convert screen coordinates to map coordinates
  screenToMap(screenX: number, screenY: number): { x: number; y: number } {
    const mapX = this.position.x + screenX / this.zoom;
    const mapY = this.position.y + screenY / this.zoom;
    return { x: mapX, y: mapY };
  }
  
  getUniforms() {
    return {
      view_x: Math.floor(this.position.x),
      view_y: Math.floor(this.position.y),
      view_width: Math.floor(this.canvasSize.width / this.zoom),
      view_height: Math.floor(this.canvasSize.height / this.zoom),
      zoom_level: this.zoom,
    };
  }
}