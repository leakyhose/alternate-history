import { useState, useEffect, useMemo } from 'react';
import type { MapMetadata, RulerFile } from '@lib/map-renderer/types';

interface CountryInfoProps {
    selectedTag: string | null;
    year: number;
    onTagChange: (tag: string) => void;
}

export default function CountryInfo( {selectedTag, year, onTagChange}: CountryInfoProps) {

    const [rulerFiles, setRulerFiles] = useState<Record<string, RulerFile>>({})
    const [metadata, setMetadata] = useState<MapMetadata | null>(null);


    // Initialization, gets list of all rulers
    useEffect(() => {

        async function fetchRulerFiles() {

            const loadedMetadata: MapMetadata = await fetch('/provinces-metadata.json').then(res => res.json());
            const rulerData: Record<string, RulerFile> = {};

            if (loadedMetadata.tags) {
                const tagNames = Object.keys(loadedMetadata.tags);
                const historyPromises = tagNames.map(async (tag) => {
                    try {
                        const res = await fetch(`/history/rulers/${tag}.json`);
                        if (res.ok) {
                            const data = await res.json();
                            return { tag, data };
                        }
                    } catch {
                        console.log(`No ruler file for ${tag}`);
                    }
                    return null;
                });

            const results = await Promise.all(historyPromises);
            for (const result of results) {
                if (result) {
                    rulerData[result.tag] = result.data;
                }
                }
            }
                    
            console.log('Loaded ruler files:', Object.keys(rulerData));
            setRulerFiles(rulerData);
            setMetadata(loadedMetadata);

        }
        fetchRulerFiles();
    }, [])

    // Auto-select ROM when selectedTag is null and data is loaded
    useEffect(() => {
        if (!selectedTag && Object.keys(rulerFiles).length > 0 && rulerFiles['ROM']) {
            console.log('Auto-selecting ROM');
            onTagChange('ROM');
        }
    }, [selectedTag, rulerFiles, onTagChange]);

    const rulerInfo = useMemo(() => {
        // Helper function to get ruler info for a tag
        const getRulerInfoForTag = (tag: string) => {
            if (!rulerFiles || !rulerFiles[tag]) return null;
            
            const rulers = rulerFiles[tag].rulers;
            if (!rulers) return null;
            
            const rulerData = rulers[year.toString()];
            if (!rulerData) return null;
            
            return rulerData;
        };

        if (!rulerFiles || !metadata || !selectedTag) {
            return { tag: null, info: null };
        }
        
        // Try to get ruler info for the selected tag
        let rulerData = getRulerInfoForTag(selectedTag);
        let effectiveTag = selectedTag;
        
        // If no ruler info, try fallback tags: ROM -> BYZ -> ROW
        if (!rulerData) {
            const fallbackTags = ['ROM', 'BYZ', 'ROW'];
            for (const fallbackTag of fallbackTags) {
                if (fallbackTag !== selectedTag) {
                    rulerData = getRulerInfoForTag(fallbackTag);
                    if (rulerData) {
                        console.log(`Falling back to ${fallbackTag}`);
                        effectiveTag = fallbackTag;
                        // Auto-switch to the fallback tag
                        onTagChange(fallbackTag);
                        break;
                    }
                }
            }
        }
        
        if (!rulerData) {
            return { tag: effectiveTag, info: null };
        }
        
        return {
            tag: effectiveTag,
            info: {
                name: rulerData.name,
                dynasty: rulerData.dynasty,
                title: rulerData.title
            }
        };
    }, [selectedTag, year, rulerFiles, metadata, onTagChange]);

    if (!rulerInfo.tag || !rulerInfo.info || !metadata) {
        return null;
    }

    const displayTag = rulerInfo.tag;
    const displayInfo = rulerInfo.info;

    return (
        <div className="absolute bottom-5 left-5 bg-[#1a1a24] border-2 border-[#2a2a3a] p-4 shadow-[inset_0_0_0_1px_#0a0a10,0_2px_0_#0a0a10] text-amber-400">
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
