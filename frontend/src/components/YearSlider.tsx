'use client'

import { useState, useRef, useEffect, useCallback } from 'react';

interface YearSliderProps {
  min?: number;
  max?: number;
  initialValue?: number;
  onChange: (year: number) => void;
}

export default function YearSlider({
  min = 2,
  max = 2000,
  initialValue = 2,
  onChange,
}: YearSliderProps) {
  const [year, setYear] = useState(initialValue);
  const [isDragging, setIsDragging] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

  const updateYear = useCallback(
    (clientX: number) => {
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const newYear = Math.round(min + percent * (max - min));
      setYear(newYear);
      onChange(newYear);
    },
    [min, max, onChange]
  );

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      e.preventDefault();
      updateYear(e.clientX);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, updateYear]);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    updateYear(e.clientX);
  };

  const percent = ((year - min) / (max - min)) * 100;

  return (
    <div className="absolute top-0 left-1/2 w-2/3 -translate-x-1/2 z-50 select-none pointer-events-auto px-4 pt-8">
      <div className="relative bg-[#1a1a24] border-2 border-[#2a2a3a] p-2 shadow-[0_2px_0_#0a0a10]">
        <div className="absolute left-1/2 -translate-x-1/2 bottom-full w-16 bg-[#1a1a24] border-2 border-b-0 border-[#2a2a3a] px-2 py-1 flex justify-center">
          <span className="text-amber-400 font-bold text-xl tracking-wide leading-none whitespace-nowrap drop-shadow-[1px_1px_0_#000]">
            {year}
          </span>
        </div>
        
        <div
          ref={trackRef}
          className="cursor-pointer relative h-2 bg-pixel-track border-[3px] border-pixel-dark shadow-[inset_0_0_0_2px_#4a4a6a]"
          onMouseDown={handleMouseDown}
        >
          <div
            className="absolute top-0 left-0 h-full bg-pixel-amber"
            style={{ width: `${percent}%` }}
          />
          
          <div
            className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-grab w-3 h-4 bg-pixel-knob border-[3px] border-pixel-dark pointer-events-auto"
            style={{ left: `${percent}%` }}
            onMouseDown={handleMouseDown}
          />
        </div>
      </div>
    </div>
  );
}
            