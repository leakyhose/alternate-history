import { useState, useEffect, useMemo } from 'react';
import type { MapMetadata, RulerHistoryEntry, RulerHistory } from '@lib/map-renderer/types';

interface CountryInfoProps {
    selectedTag: string | null;
    year: number;
}

export default function CountryInfo( {selectedTag, year}: CountryInfoProps) {

    const [rulerFiles, setRulerFiles] = useState<Record<string, RulerHistory>>({})
    const [metadata, setMetadata] = useState<MapMetadata | null>(null);


    // Initialization, gets list of all rulers
    useEffect(() => {

        async function fetchRulerFiles() {

            const loadedMetadata: MapMetadata = await fetch('/provinces-metadata.json').then(res => res.json());
            const rulerData: Record<string, RulerHistory> = {};

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

    const rulerInfo = useMemo(() => {
        if (!rulerFiles || !metadata || !selectedTag) {
            return null;
        }
        
        const tagRulers = rulerFiles[selectedTag];
        if (!tagRulers) {
            return null;
        }
        
        const rulerData = tagRulers[year.toString()];
        if (!rulerData || Array.isArray(rulerData)) {
            return null;
        }
        
        const rulerEntry = rulerData as RulerHistoryEntry;
        return {
            name: rulerEntry.name,
            dynasty: rulerEntry.dynasty,
            title: rulerEntry.title
        };
    }, [selectedTag, year, rulerFiles, metadata]);

    if (!selectedTag) {
        return null;
    }

    return (
        <div className="absolute top-20 left-4 bg-[#1a1a24] border-2 border-[#2a2a3a] p-4 shadow-[inset_0_0_0_1px_#0a0a10,0_2px_0_#0a0a10] text-amber-400">
            <h2 className="text-xl font-bold mb-2">{metadata?.tags?.[selectedTag] ? selectedTag : 'Unknown'}</h2>
            {rulerInfo && (
                <div className="space-y-1">
                    <p><span className="text-amber-600">Ruler:</span> {rulerInfo.name}</p>
                    {rulerInfo.dynasty && <p><span className="text-amber-600">Dynasty:</span> {rulerInfo.dynasty}</p>}
                    {rulerInfo.title && <p><span className="text-amber-600">Title:</span> {rulerInfo.title}</p>}
                </div>
            )}
        </div>
    );
}
