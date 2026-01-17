'use client';

import { useEffect, useRef, useState } from 'react';
import { MapGpuContext } from '@lib/map-renderer/gpu-context';
import { buildColorArray } from '@lib/map-renderer/utils';
import type { MapMetadata, SaveData, TagDefinitions } from '@lib/map-renderer/types';

export default function MapCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [gpuContext, setGpuContext] = useState<MapGpuContext | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Initialize GPU and load map
  useEffect(() => {
    async function init() {
      try {
        console.log('Initializing GPU...');
        const ctx = await MapGpuContext.create();

        console.log('Loading map data...');
        const [westRes, eastRes, metaRes] = await Promise.all([
          fetch('/provinces-west.bin'),
          fetch('/provinces-east.bin'),
          fetch('/provinces-metadata.json'),
        ]);

        const westData = new Uint16Array(await westRes.arrayBuffer());
        const eastData = new Uint16Array(await eastRes.arrayBuffer());
        const metadata: MapMetadata = await metaRes.json();

        console.log('Uploading textures...');
        await ctx.loadMapTextures(
          westData,
          eastData,
          metadata.westWidth,
          metadata.height
        );

        ctx.createColorBuffer(metadata.provinceCount);

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

  // Configure canvas
  useEffect(() => {
    if (!gpuContext || !canvasRef.current) return;

    console.log('Configuring canvas...');
    gpuContext.configureCanvas(canvasRef.current);
  }, [gpuContext]);

  // Load province colors (optional - skip if files don't exist)
  useEffect(() => {
    if (!gpuContext) return;

    async function loadColors() {
      try {
        console.log('Loading save data...');
        const [saveRes, tagsRes, metaRes] = await Promise.all([
          fetch('/save.json'),
          fetch('/tags.json'),
          fetch('/provinces-metadata.json'),
        ]);

        if (!saveRes.ok || !tagsRes.ok) {
          console.log('Save/tags files not found, using default colors');
          return;
        }

        const saveData: SaveData = await saveRes.json();
        const tagDefs: TagDefinitions = await tagsRes.json();
        const metadata: MapMetadata = await metaRes.json();

        const colors = buildColorArray(saveData, tagDefs, metadata.provinceCount);
        gpuContext!.updateProvinceColors(colors);

        console.log('✓ Colors loaded');
      } catch (err) {
        console.error('Error loading colors:', err);
      }
    }

    loadColors();
  }, [gpuContext]);

  // Render loop
  useEffect(() => {
    if (!gpuContext || !canvasRef.current) return;

    let frameId: number;

    function animate() {
      gpuContext!.render();
      frameId = requestAnimationFrame(animate);
    }

    console.log('Starting render loop...');
    animate();

    return () => cancelAnimationFrame(frameId);
  }, [gpuContext]);

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
    <canvas
      ref={canvasRef}
      width={1920}
      height={1080}
      className="w-full h-full"
    />
  );
}