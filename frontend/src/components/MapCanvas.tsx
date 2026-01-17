'use client'

import { useEffect, useRef, useState, useCallback } from 'react';
import { MapGpuContext } from '@/lib/map-renderer/gpu-context';
import type { MapMetadata, ProvinceHistoryEntry, CountryHistory } from '@/lib/map-renderer/types';
import { MapViewport } from '@/lib/map-renderer/viewport';

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
  return [0, 0, 0]; // Default black for unknown tags
}

interface MapCanvasProps {
  year?: number;
  onProvinceSelect?: (tag: string | null) => void;
}

export default function MapCanvas({ year = 2, onProvinceSelect }: MapCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [gpuContext, setGpuContext] = useState<MapGpuContext | null>(null);
  const [metadata, setMetadata] = useState<MapMetadata | null>(null);
  const [historyFiles, setHistoryFiles] = useState<Record<string, CountryHistory>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 1920, height: 1080 });
  const viewport = useRef(new MapViewport({ width: 5632, height: 2304 }));
  const isDragging = useRef(false);
  const provinceTextureData = useRef<Uint16Array | null>(null);
  const provinceToTagMap = useRef<Map<number, string>>(new Map());

  // Get color for a tag from metadata (returns dark gray for unknown tags, never 0)
  const getTagColor = useCallback((tag: string, meta: MapMetadata): number => {
    if (meta.tags && meta.tags[tag]) {
      const [r, g, b] = hexToRgb(meta.tags[tag].color);
      return packColor(r, g, b);
    }
    // Use dark gray (16,16,16) instead of black (0,0,0) so it's not confused with "no color"
    return packColor(16, 16, 16);
  }, []);

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
        const loadedMetadata: MapMetadata = await metaRes.json();

        // Uploads textures
        await ctx.loadMapTextures(
          westData,
          eastData,
          loadedMetadata.westWidth,
          loadedMetadata.height
        );

        // Store combined province data for CPU-side click detection
        const totalWidth = loadedMetadata.westWidth * 2;
        const totalHeight = loadedMetadata.height;
        const combinedData = new Uint16Array(totalWidth * totalHeight);
        
        // Copy west data
        for (let y = 0; y < totalHeight; y++) {
          const srcOffset = y * loadedMetadata.westWidth;
          const dstOffset = y * totalWidth;
          combinedData.set(westData.subarray(srcOffset, srcOffset + loadedMetadata.westWidth), dstOffset);
        }
        
        // Copy east data
        for (let y = 0; y < totalHeight; y++) {
          const srcOffset = y * loadedMetadata.westWidth;
          const dstOffset = y * totalWidth + loadedMetadata.westWidth;
          combinedData.set(eastData.subarray(srcOffset, srcOffset + loadedMetadata.westWidth), dstOffset);
        }
        
        provinceTextureData.current = combinedData;

        ctx.createUniformBuffer(loadedMetadata.westWidth, loadedMetadata.height, loadedMetadata.provinceCount);
        ctx.createColorBuffers(loadedMetadata.provinceCount);

        // Load history files for all tags in metadata
        const historyData: Record<string, CountryHistory> = {};
        if (loadedMetadata.tags) {
          const tagNames = Object.keys(loadedMetadata.tags);
          const historyPromises = tagNames.map(async (tag) => {
            try {
              const res = await fetch(`/history/provinces/${tag}.json`);
              if (res.ok) {
                const data = await res.json();
                return { tag, data };
              }
            } catch {
              console.log(`No history file for ${tag}`);
            }
            return null;
          });
          
          const results = await Promise.all(historyPromises);
          for (const result of results) {
            if (result) {
              historyData[result.tag] = result.data;
            }
          }
        }
        
        console.log('Loaded history files:', Object.keys(historyData));
        setHistoryFiles(historyData);
        setMetadata(loadedMetadata);

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

  // Update map colors when year changes
  useEffect(() => {
    if (!gpuContext || !metadata || Object.keys(historyFiles).length === 0) return;

    const seaProvinces = new Set(metadata.seaProvinces || []);
    const defaultLandColor = packColor(173, 150, 116);
    const seaColor = packColor(61, 66, 107);

    const primaryColors = new Uint32Array(metadata.provinceCount);
    const ownerColors = new Uint32Array(metadata.provinceCount);
    const secondaryColors = new Uint32Array(metadata.provinceCount);

    // Initialize all provinces
    for (let i = 0; i < metadata.provinceCount; i++) {
      if (seaProvinces.has(i)) {
        primaryColors[i] = seaColor;
        ownerColors[i] = seaColor;
        secondaryColors[i] = 0; // No stripes for sea
      } else {
        primaryColors[i] = defaultLandColor;
        ownerColors[i] = defaultLandColor;
        secondaryColors[i] = 0;
      }
    }

    // Apply historical data for each country
    const yearStr = String(year);
    provinceToTagMap.current.clear();
    for (const [tag, history] of Object.entries(historyFiles)) {
      const yearData = history[yearStr] as ProvinceHistoryEntry[] | undefined;
      if (!yearData || !Array.isArray(yearData)) continue;

      const tagColor = getTagColor(tag, metadata);

      for (const province of yearData) {
        const provId = province.ID;
        if (provId >= metadata.provinceCount || seaProvinces.has(provId)) continue;

        // Map province to its owning tag
        provinceToTagMap.current.set(provId, tag);

        // Set province color to tag's color
        primaryColors[provId] = tagColor;
        ownerColors[provId] = tagColor;

        // Handle occupation
        if (province.CONTROL && province.CONTROL !== '') {
          // Province is occupied - show stripes with occupier's color
          const occupierColor = getTagColor(province.CONTROL, metadata);
          secondaryColors[provId] = occupierColor;
        } else {
          secondaryColors[provId] = 0; // No occupation, no stripes
        }
      }
    }

    gpuContext.updateProvinceColors(primaryColors);
    gpuContext.updateOwnerColors(ownerColors);
    gpuContext.updateSecondaryColors(secondaryColors);
    console.log(`Map updated for year ${year}`);
  }, [year, gpuContext, metadata, historyFiles, getTagColor]);

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
    if (!canvas || isLoading) return;

    let mouseDownPos: { x: number; y: number } | null = null;

    const onMouseDown = (e: MouseEvent) => {
      if (e.button === 0) { // Left click only
        isDragging.current = false;
        mouseDownPos = { x: e.clientX, y: e.clientY };
      }
    };

    const onMouseUp = (e: MouseEvent) => {
      if (e.button === 0 && mouseDownPos) {
        const dragDistance = Math.sqrt(
          Math.pow(e.clientX - mouseDownPos.x, 2) + 
          Math.pow(e.clientY - mouseDownPos.y, 2)
        );
        
        // Only treat as click if drag distance is very small (< 5 pixels)
        if (dragDistance < 5 && onProvinceSelect && provinceTextureData.current && metadata) {
          // Click without drag - select province
          const rect = canvas.getBoundingClientRect();
          const canvasX = e.clientX - rect.left;
          const canvasY = e.clientY - rect.top;
          
          // Convert canvas coordinates to map coordinates using viewport
          const mapCoords = viewport.current.screenToMap(canvasX, canvasY);
          const mapX = Math.floor(mapCoords.x);
          const mapY = Math.floor(mapCoords.y);
          
          // Get province ID from texture data
          const totalWidth = metadata.westWidth * 2;
          if (mapX >= 0 && mapX < totalWidth && mapY >= 0 && mapY < metadata.height) {
            const index = mapY * totalWidth + mapX;
            const provinceId = provinceTextureData.current[index];
            
            // Find the tag that owns this province
            const owningTag = provinceToTagMap.current.get(provinceId);
            console.log(`Clicked province ${provinceId}, owned by: ${owningTag || 'none'}`);
            
            // Only update selection if the province is owned by a tag
            if (owningTag) {
              onProvinceSelect(owningTag);
            }
          }
        }
        
        isDragging.current = false;
        mouseDownPos = null;
      }
    };

    const onMouseMove = (e: MouseEvent) => {
      if (mouseDownPos) {
        const dragDistance = Math.sqrt(
          Math.pow(e.clientX - mouseDownPos.x, 2) + 
          Math.pow(e.clientY - mouseDownPos.y, 2)
        );
        
        if (dragDistance > 5 && !isDragging.current) {
          isDragging.current = true;
        }
        
        if (isDragging.current) {
          viewport.current.pan(-e.movementX, -e.movementY);
        }
      }
    };


    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const zoomDelta = e.deltaY > 0 ? 0.9 : 1.1;
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
  }, [isLoading, onProvinceSelect, metadata]);

  
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
    <div ref={containerRef} className="w-full h-full overflow-hidden bg-black">
      <canvas
        ref={canvasRef}
        width={canvasSize.width}
        height={canvasSize.height}
        className="block bg-black"
      />
    </div>
  );
}