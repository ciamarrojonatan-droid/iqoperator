"use client";

import React, { useEffect, useState } from "react";
import { Volume2, VolumeX, Sparkles, Music } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  initAudioContext,
  playCallSound,
  playPutSound,
  playTestChime,
  getAudioEnabled,
  setAudioEnabled,
} from "@/lib/audio-alerts";

export function AudioToggle({
  className,
  onStateChange,
}: {
  className?: string;
  onStateChange?: (enabled: boolean) => void;
}) {
  const [enabled, setEnabled] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  useEffect(() => {
    const isSaved = getAudioEnabled();
    setEnabled(isSaved);
    if (onStateChange) onStateChange(isSaved);
  }, []);

  function toggleAudio() {
    const nextState = !enabled;
    setEnabled(nextState);
    setAudioEnabled(nextState);
    if (onStateChange) onStateChange(nextState);

    if (nextState) {
      initAudioContext();
      playTestChime();
    }
  }

  function handleTestCall(e: React.MouseEvent) {
    e.stopPropagation();
    initAudioContext();
    playCallSound();
  }

  function handleTestPut(e: React.MouseEvent) {
    e.stopPropagation();
    initAudioContext();
    playPutSound();
  }

  return (
    <div className={cn("relative inline-flex items-center", className)}>
      <div className="flex items-center rounded-lg border border-border bg-surface p-0.5 shadow-sm">
        <button
          type="button"
          onClick={toggleAudio}
          title={enabled ? "Desativar avisos sonoros" : "Ativar avisos sonoros de sinais"}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all select-none",
            enabled
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.2)]"
              : "text-muted hover:text-foreground hover:bg-surface-elevated border border-transparent"
          )}
        >
          {enabled ? (
            <>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <Volume2 size={14} className="text-emerald-400" />
              <span className="font-semibold">Áudio ON</span>
            </>
          ) : (
            <>
              <VolumeX size={14} className="text-muted" />
              <span>Áudio OFF</span>
            </>
          )}
        </button>

        {/* Mini test trigger */}
        <button
          type="button"
          onClick={() => setShowMenu((prev) => !prev)}
          title="Opções e teste de sons"
          className="px-1.5 py-1 text-muted hover:text-foreground rounded transition-colors text-[11px]"
        >
          <Music size={12} />
        </button>
      </div>

      {/* Popover de Teste de Sons */}
      {showMenu && (
        <div
          className="absolute right-0 top-full mt-2 w-52 p-2.5 bg-surface-elevated border border-border rounded-lg shadow-xl z-50 flex flex-col gap-2 text-xs"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between pb-1 border-b border-border/60">
            <span className="font-semibold text-foreground flex items-center gap-1.5">
              <Sparkles size={12} className="text-accent" />
              Testar Alertas
            </span>
            <button
              onClick={() => setShowMenu(false)}
              className="text-muted hover:text-foreground text-[10px]"
            >
              ✕
            </button>
          </div>
          <p className="text-[11px] text-muted leading-tight">
            Toca automaticamente quando a IA aprova um novo sinal válido.
          </p>
          <div className="grid grid-cols-2 gap-1.5 pt-1">
            <button
              type="button"
              onClick={handleTestCall}
              className="px-2 py-1.5 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/20 transition-all text-center"
            >
              Som CALL ↑
            </button>
            <button
              type="button"
              onClick={handleTestPut}
              className="px-2 py-1.5 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-semibold border border-rose-500/20 transition-all text-center"
            >
              Som PUT ↓
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
