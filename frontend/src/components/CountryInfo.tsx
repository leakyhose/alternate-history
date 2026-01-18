'use client'

import { useEffect, useMemo } from 'react';
import type { RulerHistory, ScenarioMetadata } from '@/types'

interface CountryInfoProps {
    defaultRulerHistory: RulerHistory | null
    scenarioMetadata: ScenarioMetadata | null
    selectedTag: string | null;
    year: number;
    onTagChange: (tag: string) => void;
}

export default function CountryInfo({
    defaultRulerHistory,
    scenarioMetadata,
    selectedTag,
    year,
    onTagChange
}: CountryInfoProps) {

    // Get ordered list of tags from scenario metadata
    const availableTags = useMemo(() => {
        if (!scenarioMetadata?.tags) return []
        return Object.keys(scenarioMetadata.tags)
    }, [scenarioMetadata])

    // Auto-select first available tag when none selected
    useEffect(() => {
        if (!selectedTag && defaultRulerHistory && scenarioMetadata) {
            const yearData = defaultRulerHistory[year.toString()];
            if (yearData && Array.isArray(yearData)) {
                // Try first tag in ruler data for this year
                const firstRuler = yearData[0];
                if (firstRuler) {
                    console.log(`Auto-selecting ${firstRuler.TAG}`);
                    onTagChange(firstRuler.TAG);
                }
            }
        }
    }, [selectedTag, defaultRulerHistory, scenarioMetadata, year, onTagChange]);

    const rulerInfo = useMemo(() => {
        if (!defaultRulerHistory || !scenarioMetadata || !selectedTag) {
            return { tag: null, info: null };
        }

        const yearData = defaultRulerHistory[year.toString()];
        if (!yearData || !Array.isArray(yearData)) {
            return { tag: selectedTag, info: null };
        }

        // Find ruler for the selected tag
        let ruler = yearData.find((r: any) => r.TAG === selectedTag);
        let effectiveTag = selectedTag;

        // If no ruler info, fallback to iterate through available tags in order
        if (!ruler) {
            for (const fallbackTag of availableTags) {
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
                title: ruler.TITLE,
                age: ruler.AGE
            }
        };
    }, [selectedTag, year, defaultRulerHistory, scenarioMetadata, availableTags, onTagChange]);

    if (!rulerInfo.tag || !rulerInfo.info || !scenarioMetadata) {
        return null;
    }

    const displayTag = rulerInfo.tag;
    const displayInfo = rulerInfo.info;

    return (
        <div className="absolute bottom-5 left-5 min-w-60 max-w-72 bg-[#1a1a24] border-2 border-[#2a2a3a] p-4 shadow-[inset_0_0_0_1px_#0a0a10,0_2px_0_#0a0a10] text-amber-400">
            {/* Country Name */}
            <h2 className="text-3xl font-bold text-center tracking-wide">
                {scenarioMetadata.tags[displayTag]?.name || displayTag}
            </h2>

            <div className="border-t border-[#2a2a3a] my-3"></div>

            {/* Ruler */}
            <div className="text-center">
                <div className={`font-semibold leading-tight ${displayInfo.name.length > 15 ? 'text-4xl' : 'text-5xl'}`}>
                    {displayInfo.name}
                </div>
                <div className="text-amber-600 text-sm mt-1">
                    {displayInfo.dynasty} dynasty · {displayInfo.age} years old
                </div>
            </div>
        </div>
    );
}
