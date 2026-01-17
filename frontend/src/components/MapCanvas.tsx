'use client';

import { useEffect, useRef, useState } from 'react';
import { MapGpuContext } from '@lib/map-renderer/gpu-context';
import type { MapMetadata } from '@lib/map-renderer/types';
import { MapViewport } from '@lib/map-renderer/viewport';

// Pack RGB to u32 (0x00RRGGBB)
function packColor(r: number, g: number, b: number): number {
  return (r << 16) | (g << 8) | b;
}

// Parse hex color to RGB
function hexToRgb(hex: string): [number, number, number] {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (result) {
    return [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)];
  }
  return [128, 128, 128]; // Default gray
}

export default function MapCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [gpuContext, setGpuContext] = useState<MapGpuContext | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 1920, height: 1080 });
  const viewport = useRef(new MapViewport({ width: 5632, height: 2304 }));
  const isDragging = useRef(false);


  // Initialize GPU and load map
  useEffect(() => {
    async function init() {
      try {
        // Initalizes GPU
        const ctx = await MapGpuContext.create();

        console.log('Loading map data...');
        const [westRes, eastRes, metaRes] = await Promise.all([
          fetch('/provinces-west.bin'),
          fetch('/provinces-east.bin'),
          fetch('/provinces-metadata.json'),
        ]);

        // Fetches Data
        const westData = new Uint16Array(await westRes.arrayBuffer());
        const eastData = new Uint16Array(await eastRes.arrayBuffer());
        const metadata: MapMetadata = await metaRes.json();

        // Uploads textures
        await ctx.loadMapTextures(
          westData,
          eastData,
          metadata.westWidth,
          metadata.height
        );

        ctx.createUniformBuffer(metadata.westWidth, metadata.height, metadata.provinceCount);
        ctx.createColorBuffers(metadata.provinceCount);

        // Generate country colors from metadata
        const primaryColors = new Uint32Array(metadata.provinceCount);
        const ownerColors = new Uint32Array(metadata.provinceCount);
        
        // Default: gray for all provinces
        const defaultLandColor = packColor(94, 94, 94);
        const seaColor = packColor(68, 107, 163); // EU4 style blue
        
        // Sea provinces list (from definition.csv - provinces containing Sea, Ocean, Lake, Gulf, Bay, etc.)
        // These are scattered throughout the file, not contiguous
        const seaProvinces = new Set(metadata.seaProvinces || []);
        
        for (let i = 0; i < metadata.provinceCount; i++) {
          if (seaProvinces.has(i)) {
            // Sea province - blue color, same "owner" so no borders between sea
            primaryColors[i] = seaColor;
            ownerColors[i] = seaColor;
          } else {
            primaryColors[i] = defaultLandColor;
            ownerColors[i] = defaultLandColor;
          }
        }
        
        // Assign country colors (only for land provinces)
        if (metadata.countries) {
          for (const [, country] of Object.entries(metadata.countries)) {
            const [r, g, b] = hexToRgb(country.color);
            const color = packColor(r, g, b);
            
            for (const provId of country.provinces) {
              if (!seaProvinces.has(provId) && provId < metadata.provinceCount) {
                primaryColors[provId] = color;
                ownerColors[provId] = color;
              }
            }
          }
        }
        
        ctx.updateProvinceColors(primaryColors);
        ctx.updateOwnerColors(ownerColors);
        console.log('✓ Country colors loaded');

        const format = navigator.gpu.getPreferredCanvasFormat();
        await ctx.createRenderPipeline(format);

        setGpuContext(ctx);
        setIsLoading(false);
      } catch (err) {
        console.error('Initialization error:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
        setIsLoading(false);
      }
    }

    init();
  }, []);

  // Configure canvas and handle resize
  useEffect(() => {
    if (!gpuContext || !canvasRef.current || !containerRef.current) return;

    const updateSize = () => {
      const container = containerRef.current!;
      const width = container.clientWidth;
      const height = container.clientHeight;
      
      setCanvasSize({ width, height });
      viewport.current.resize(width, height);
      viewport.current.fitToScreen();
      gpuContext.configureCanvas(canvasRef.current!, width, height);
      console.log(`Canvas configured: ${width}x${height}`);
    };

    updateSize();

    const resizeObserver = new ResizeObserver(updateSize);
    resizeObserver.observe(containerRef.current);

    return () => resizeObserver.disconnect();
  }, [gpuContext]);



  // Render loop
  useEffect(() => {
    if (!gpuContext || !canvasRef.current) return;

    let frameId: number;

    function animate() {
      // Update GPU with current viewport
      const uniforms = viewport.current.getUniforms();
      gpuContext!.updateUniforms({
        x: uniforms.view_x,
        y: uniforms.view_y,
        width: uniforms.view_width,
        height: uniforms.view_height,
        zoom: uniforms.zoom_level,
      });
      gpuContext!.render();
      frameId = requestAnimationFrame(animate);
    }

    console.log('Starting render loop...');
    animate();

    return () => cancelAnimationFrame(frameId);
  }, [gpuContext]);

  // Mouse/wheel event handlers
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onMouseDown = (e: MouseEvent) => {
      if (e.button === 0) { // Left click only
        isDragging.current = true;
        console.log('Mouse down - dragging started');
      }
    };

    const onMouseUp = () => {
      if (isDragging.current) {
        console.log('Mouse up - dragging stopped');
      }
      isDragging.current = false;
    };

    const onMouseMove = (e: MouseEvent) => {
      if (isDragging.current) {
        console.log(`Panning: dx=${e.movementX}, dy=${e.movementY}`);
        viewport.current.pan(-e.movementX, -e.movementY);
      }
    };

    

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const zoomDelta = e.deltaY > 0 ? 0.9 : 1.1;
      console.log(`Zoom: delta=${zoomDelta}`);
      viewport.current.zoomAt(e.offsetX, e.offsetY, zoomDelta);
    };

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('mouseleave', onMouseUp);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('wheel', onWheel, { passive: false });

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown);
      canvas.removeEventListener('mouseup', onMouseUp);
      canvas.removeEventListener('mouseleave', onMouseUp);
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('wheel', onWheel);
    };
  }, [isLoading]); // Re-run when loading completes so canvas exists

  
  if (error) {
    return (
      <div className="flex items-center justify-center w-full h-full bg-red-950 text-red-200">
        <div className="text-center">
          <h2 className="text-xl font-bold mb-2">WebGPU Error</h2>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center w-full h-full bg-gray-900 text-gray-200">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4" />
          <p>Loading map...</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full overflow-hidden">
      <canvas
        ref={canvasRef}
        width={canvasSize.width}
        height={canvasSize.height}
        className="block"
      />
    </div>
  );
}