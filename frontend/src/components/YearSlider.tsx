'use client';

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
    <div className="absolute top-0 left-0 w-full z-50 h-10 bg-gray-900 flex items-center px-4 select-none" style={{ width: '100vw' }}>
      <span className="text-gray-400 text-xs shrink-0">{min}</span>
      
      <div
        ref={trackRef}
        className="grow mx-2 h-3 bg-gray-700 rounded cursor-pointer relative"
        onMouseDown={handleMouseDown}
      >
        <div
          className="absolute top-0 left-0 h-full bg-amber-500 rounded-l"
          style={{ width: `${percent}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white rounded-full shadow-lg cursor-grab border-2 border-amber-500"
          style={{ left: `calc(${percent}% - 10px)` }}
          onMouseDown={handleMouseDown}
        />
      </div>
      
      <span className="text-gray-400 text-xs shrink-0">{max}</span>
      <span className="text-amber-400 text-lg font-bold ml-3 shrink-0">{year}</span>
    </div>
  );
}