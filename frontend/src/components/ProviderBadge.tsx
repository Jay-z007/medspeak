import React from "react";

interface ProviderBadgeProps {
  provider?: string | null;
  isFallback?: boolean;
  isConnected?: boolean;
}

export const ProviderBadge: React.FC<ProviderBadgeProps> = ({
  provider = null,
  isFallback = false,
  isConnected = true,
}) => {
  if (!isConnected || !provider) {
    return (
      <div
        className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold tracking-wide border bg-rose-500/10 text-rose-400 border-rose-500/30"
        role="status"
        aria-label="Voice Provider: Disconnected"
      >
        <span className="w-2 h-2 rounded-full bg-rose-500" />
        <span>Voice: Disconnected</span>
      </div>
    );
  }

  const displayName = provider.charAt(0).toUpperCase() + provider.slice(1);

  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold tracking-wide border ${
        isFallback
          ? "bg-amber-500/10 text-amber-500 border-amber-500/30"
          : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
      }`}
      role="status"
      aria-label={`Voice Provider: ${displayName}${isFallback ? " (Fallback active)" : ""}`}
    >
      <span
        className={`w-2 h-2 rounded-full ${
          isFallback ? "bg-amber-500 animate-pulse" : "bg-emerald-400"
        }`}
      />
      <span>Voice: {displayName}</span>
      {isFallback && <span className="text-[10px] uppercase opacity-75">(Fallback)</span>}
    </div>
  );
};
