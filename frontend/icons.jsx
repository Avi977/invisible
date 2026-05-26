// Inline SVG icons — single source so we don't fight with icon fonts.
// Each Icon component takes size + optional className/style.
const Ico = (paths, vb = "0 0 24 24") => ({ size = 16, stroke = "currentColor", fill = "none", ...rest }) => (
  <svg width={size} height={size} viewBox={vb} fill={fill} stroke={stroke}
       strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...rest}>
    {paths}
  </svg>
);

const I = {
  Dashboard: Ico(<><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></>),
  Folder:    Ico(<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>),
  Graph:     Ico(<><circle cx="6" cy="6" r="2.2"/><circle cx="18" cy="6" r="2.2"/><circle cx="12" cy="18" r="2.2"/><circle cx="18" cy="14" r="2.2"/><path d="M7.5 7.5 11 16.5M16.5 7.5 13 16.5M14 18l2.5-2.5M8 6h8"/></>),
  Terminal:  Ico(<><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/></>),
  Tools:     Ico(<><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h8M6 8v8M18 8v8M8 18h8"/></>),
  Calendar:  Ico(<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/><circle cx="8" cy="14" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="14" r="1" fill="currentColor" stroke="none"/></>),
  ChevronL:  Ico(<path d="m15 18-6-6 6-6"/>),
  ChevronR:  Ico(<path d="m9 6 6 6-6 6"/>),
  ChevronD:  Ico(<path d="m6 9 6 6 6-6"/>),
  Plus:      Ico(<><path d="M12 5v14M5 12h14"/></>),
  Search:    Ico(<><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></>),
  Settings:  Ico(<><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.66 15a1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.66 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.66a1.7 1.7 0 0 0 1.03-1.56V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15 4.66a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.34 9 1.7 1.7 0 0 0 21 10.03H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.56 1.03Z"/></>),
  Sparkles:  Ico(<><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2 2M16.4 16.4l2 2M5.6 18.4l2-2M16.4 7.6l2-2"/><circle cx="12" cy="12" r="2" fill="currentColor" stroke="none"/></>),
  Send:      Ico(<path d="m4 12 16-8-6 17-3-7-7-2z"/>),
  X:         Ico(<path d="M6 6l12 12M18 6 6 18"/>),
  Doc:       Ico(<><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 14h8M8 18h5"/></>),
  GitHub:    Ico(<path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.15-1.1-1.46-1.1-1.46-.9-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.53 2.34 1.09 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.56-1.11-4.56-4.95 0-1.1.39-2 1.03-2.7-.1-.26-.45-1.28.1-2.66 0 0 .84-.27 2.75 1.03a9.5 9.5 0 0 1 5 0c1.91-1.3 2.75-1.03 2.75-1.03.55 1.38.2 2.4.1 2.66.64.7 1.03 1.6 1.03 2.7 0 3.85-2.34 4.7-4.57 4.95.36.31.68.92.68 1.86v2.76c0 .27.18.58.69.48A10 10 0 0 0 12 2z" fill="currentColor" stroke="none"/>),
  Server:    Ico(<><rect x="3" y="4" width="18" height="6" rx="1.5"/><rect x="3" y="14" width="18" height="6" rx="1.5"/><circle cx="7" cy="7" r="1" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="1" fill="currentColor" stroke="none"/></>),
  HardDrive: Ico(<><rect x="3" y="13" width="18" height="8" rx="2"/><path d="m4 13 3-7a2 2 0 0 1 1.8-1h6.4a2 2 0 0 1 1.8 1l3 7M7 17h.01M11 17h.01"/></>),
  Globe:     Ico(<><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></>),
  Box:       Ico(<><path d="m21 8-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8M12 13v8"/></>),
  Code:      Ico(<><path d="m8 6-6 6 6 6M16 6l6 6-6 6"/></>),
  Layers:    Ico(<><path d="m12 2 10 5-10 5L2 7l10-5z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/></>),
  File:      Ico(<><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></>),
  Play:      Ico(<path d="M6 4v16l14-8z" fill="currentColor"/>),
  Star:      Ico(<path d="m12 2 3 7 7 .8-5.3 4.7L18 22l-6-3.3L6 22l1.3-7.5L2 9.8 9 9z"/>),
  Bell:      Ico(<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></>),
  CheckCircle: Ico(<><circle cx="12" cy="12" r="9"/><path d="m9 12 2 2 4-5"/></>),
  Clock:     Ico(<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>),
  Hash:      Ico(<><path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/></>),
  Target:    Ico(<><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/></>),
  RefreshCw: Ico(<><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></>),
  Lock:      Ico(<><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></>),
  Dots:      Ico(<><circle cx="6"  cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="18" cy="12" r="1.5" fill="currentColor" stroke="none"/></>),
  Pause:     Ico(<><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></>),
  BarChart:  Ico(<><path d="M3 21h18"/><rect x="6"  y="11" width="3" height="8" rx="0.5"/><rect x="11" y="7"  width="3" height="12" rx="0.5"/><rect x="16" y="3"  width="3" height="16" rx="0.5"/></>),
  TrendUp:   Ico(<><path d="m3 17 6-6 4 4 8-8"/><path d="M14 7h7v7"/></>),
  Zap:       Ico(<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/>),
  Coin:      Ico(<><circle cx="12" cy="12" r="9"/><path d="M12 6v12M8 9h6a2 2 0 0 1 0 4H10a2 2 0 0 0 0 4h6"/></>),
};

Object.assign(window, { I });
