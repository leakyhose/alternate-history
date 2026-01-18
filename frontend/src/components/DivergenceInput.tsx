'use client'

import { useState, useRef, useEffect } from 'react'

interface DivergenceInputProps {
  onSubmit: (command: string, yearsToProgress: number) => void
  disabled: boolean
  isProcessing: boolean
  error?: string | null
  alternative?: string | null
  currentYear?: number
  isAddingDivergence?: boolean  // True when adding to existing timeline
}

export default function DivergenceInput({
  onSubmit,
  disabled,
  isProcessing,
  error,
  alternative,
  currentYear,
  isAddingDivergence
}: DivergenceInputProps) {
  const [command, setCommand] = useState('')
  const [yearsToProgress, setYearsToProgress] = useState(25)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-focus input when not disabled
  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus()
    }
  }, [disabled])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (command.trim() && !disabled && !isProcessing) {
      onSubmit(command.trim(), yearsToProgress)
      setCommand('')  // Clear input after submission
    }
  }

  return (
    <div className="absolute bottom-5 left-1/2 -translate-x-1/2 w-[500px] max-w-[90vw] bg-[#1a1a24]/95 border-2 border-[#2a2a3a] p-3 z-30 rounded shadow-lg">
      {/* Error/Alternative display */}
      {error && (
        <div className="mb-2 p-2 bg-red-900/50 border border-red-700 rounded text-red-200 text-xs">
          <span className="font-bold">Rejected: </span>{error}
          {alternative && (
            <div className="mt-1 text-amber-300">
              <span className="font-bold">Try: </span>{alternative}
            </div>
          )}
        </div>
      )}

      {/* Processing indicator */}
      {isProcessing && (
        <div className="mb-2 flex items-center gap-2 text-amber-400 text-sm">
          <div className="animate-pulse">●</div>
          <span>Processing divergence...</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2 items-center">
        {/* Current year indicator when adding divergence to existing timeline */}
        {isAddingDivergence && currentYear && (
          <div className="text-amber-400 font-bold whitespace-nowrap text-sm">
            {currentYear} AD
          </div>
        )}

        {/* Divergence input */}
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder={isAddingDivergence 
              ? `Add a new divergence from ${currentYear} AD...` 
              : "Enter a what-if scenario..."}
            disabled={disabled || isProcessing}
            className="w-full bg-[#0a0a14] border border-[#2a2a3a] text-amber-100 px-3 py-2 rounded text-sm
                       placeholder:text-gray-500 focus:border-amber-500/50 focus:outline-none
                       disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        {/* Years selector */}
        <div className="flex items-center gap-1">
          <label className="text-amber-400 text-xs whitespace-nowrap">Years:</label>
          <select
            value={yearsToProgress}
            onChange={(e) => setYearsToProgress(Number(e.target.value))}
            disabled={disabled || isProcessing}
            className="bg-[#0a0a14] border border-[#2a2a3a] text-amber-100 px-2 py-2 rounded text-sm
                       focus:border-amber-500/50 focus:outline-none
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
          </select>
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={disabled || isProcessing || !command.trim()}
          className="bg-amber-600 hover:bg-amber-500 text-black font-bold px-4 py-2 rounded text-sm
                     disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed
                     transition-colors"
        >
          {isProcessing ? '...' : isAddingDivergence ? 'Add' : 'Start'}
        </button>
      </form>
    </div>
  )
}
