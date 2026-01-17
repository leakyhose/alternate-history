'use client'

import { useState, useEffect, useMemo } from 'react';
import type { RulerHistory, MapMetadata } from '@/types'

interface CountryInfoProps {
    defaultRulerHistory: RulerHistory | null
    selectedTag: string | null;
    year: number;
    onTagChange: (tag: string) => void;
}

export default function CountryInfo({ defaultRulerHistory, selectedTag, year, onTagChange }: CountryInfoProps) {

    const [metadata, setMetadata] = useState<MapMetadata | null>(null);

    // Fetch metadata for tag display names
    useEffect(() => {
        fetch('/provinces-metadata.json')
            .then(res => res.json())
            .then(data => setMetadata(data))
            .catch(err => console.error('Failed to load metadata:', err));
    }, []);

    // Auto-select ROM when selectedTag is null and data is loaded
    useEffect(() => {
        if (!selectedTag && defaultRulerHistory && metadata) {
            const yearData = defaultRulerHistory[year.toString()];
            if (yearData && Array.isArray(yearData)) {
                const romRuler = yearData.find((r: any) => r.TAG === 'ROM');
                if (romRuler) {
                    console.log('Auto-selecting ROM');
                    onTagChange('ROM');
                }
            }
        }
    }, [selectedTag, defaultRulerHistory, metadata, year, onTagChange]);

    const rulerInfo = useMemo(() => {
        if (!defaultRulerHistory || !metadata || !selectedTag) {
            return { tag: null, info: null };
        }

        const yearData = defaultRulerHistory[year.toString()];
        if (!yearData || !Array.isArray(yearData)) {
            return { tag: selectedTag, info: null };
        }

        // Find ruler for the selected tag (JSON uses uppercase keys)
        let ruler = yearData.find((r: any) => r.TAG === selectedTag);
        let effectiveTag = selectedTag;

        // If no ruler info, try fallback tags: ROM -> BYZ -> ROW
        if (!ruler) {
            const fallbackTags = ['ROM', 'BYZ', 'ROW'];
            for (const fallbackTag of fallbackTags) {
                if (fallbackTag !== selectedTag) {
                    ruler = yearData.find((r: any) => r.TAG === fallbackTag);
                    if (ruler) {
                        console.log(`Falling back to ${fallbackTag}`);
                        effectiveTag = fallbackTag;
                        onTagChange(fallbackTag);
                        break;
                    }
                }
            }
        }

        if (!ruler) {
            return { tag: effectiveTag, info: null };
        }

        return {
            tag: effectiveTag,
            info: {
                name: ruler.NAME,
                dynasty: ruler.DYNASTY,
                title: ruler.TITLE
            }
        };
    }, [selectedTag, year, defaultRulerHistory, metadata, onTagChange]);

    if (!rulerInfo.tag || !rulerInfo.info || !metadata) {
        return null;
    }

    const displayTag = rulerInfo.tag;
    const displayInfo = rulerInfo.info;

    return (
        <div className="absolute bottom-5 left-5 w-60 bg-[#1a1a24] border-2 border-[#2a2a3a] p-4 shadow-[inset_0_0_0_1px_#0a0a10,0_2px_0_#0a0a10] text-amber-400">
            <h2 className=" text-4xl font-bold mb-2 text-center">{metadata?.tags![displayTag]?.name || displayTag}</h2>
            <div className="space-y-1 text-2xl text-center">
                <p><div className="text-amber-600 text-lg">Emperor</div>
                    <div className='text-3xl'>{displayInfo.name}</div>
                    <div className="text-lg text-amber-600">of the </div> 
                    <div className='text-2xl'>{displayInfo.dynasty}</div>
                    <div className="text-lg text-amber-600">dynasty</div></p>
            </div>
        </div>
    );
}
