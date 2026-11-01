import React from "react";
import { Check, Sparkles, Video, BarChart3, User, Palette, Smile } from "lucide-react";
import type { VideoStyle } from "../types";

export interface StyleDefinition {
  value: VideoStyle;
  titleKey: string;
  aboutKey: string;
  badge: string;
  idealFor: string;
  howItWorks: string;
  thumbnail: React.ReactNode;
}

export const STYLE_DEFINITIONS: StyleDefinition[] = [
  {
    value: "auto",
    titleKey: "tf.style.auto",
    aboutKey: "tf.style.auto.about",
    badge: "AI Directed",
    idealFor: "Podcasts, general narration, educational summaries",
    howItWorks: "Smartly mixes charts, stick figures, and motion text based on context",
    thumbnail: (
      <svg viewBox="0 0 320 180" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="auto-bg" x1="0" y1="0" x2="320" y2="180" gradientUnits="userSpaceOnUse">
            <stop stopColor="#1e1b4b" />
            <stop offset="0.5" stopColor="#311042" />
            <stop offset="1" stopColor="#0f172a" />
          </linearGradient>
          <linearGradient id="auto-glow" x1="160" y1="40" x2="160" y2="140" gradientUnits="userSpaceOnUse">
            <stop stopColor="#ec4899" stopOpacity="0.8" />
            <stop offset="1" stopColor="#8b5cf6" stopOpacity="0.2" />
          </linearGradient>
        </defs>
        <rect width="320" height="180" fill="url(#auto-bg)" />
        {/* Subtle grid pattern */}
        <path d="M0 45h320M0 90h320M0 135h320M80 0v180M160 0v180M240 0v180" stroke="#ffffff" strokeOpacity="0.05" strokeWidth="1" />
        
        {/* Glowing Orb */}
        <circle cx="160" cy="85" r="48" fill="url(#auto-glow)" filter="blur(16px)" />
        
        {/* Central AI Diamond / Sparkle */}
        <path d="M160 52 L172 80 L200 85 L172 90 L160 118 L148 90 L120 85 L148 80 Z" fill="#ffffff" />
        <circle cx="160" cy="85" r="8" fill="#ec4899" />
        
        {/* Surrounding multi-style badges */}
        {/* Mini Chart */}
        <g transform="translate(42, 60)">
          <rect width="64" height="48" rx="6" fill="#1e293b" fillOpacity="0.8" stroke="#38bdf8" strokeWidth="1.5" />
          <rect x="12" y="24" width="8" height="16" rx="2" fill="#38bdf8" />
          <rect x="26" y="16" width="8" height="24" rx="2" fill="#818cf8" />
          <rect x="40" y="8" width="8" height="32" rx="2" fill="#c084fc" />
        </g>
        {/* Mini Character */}
        <g transform="translate(216, 56)">
          <rect width="64" height="52" rx="6" fill="#1e293b" fillOpacity="0.8" stroke="#fbbf24" strokeWidth="1.5" />
          <circle cx="28" cy="20" r="7" stroke="#fbbf24" strokeWidth="2" />
          <path d="M28 27v14M28 32l-7-4M28 32l8-3M28 41l-6 8M28 41l7 8" stroke="#fbbf24" strokeWidth="2" strokeLinecap="round" />
          <path d="M44 16h12M44 22h8" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" />
        </g>
        
        {/* Bottom context pill */}
        <rect x="85" y="142" width="150" height="22" rx="11" fill="#0f172a" fillOpacity="0.9" stroke="#8b5cf6" strokeWidth="1" />
        <text x="160" y="157" fill="#e2e8f0" fontSize="10" fontWeight="600" textAnchor="middle" letterSpacing="0.5">CONTEXT-AWARE AI</text>
      </svg>
    ),
  },
  {
    value: "mixed",
    titleKey: "tf.style.mixed",
    aboutKey: "tf.style.mixed.about",
    badge: "Video + Motion",
    idealFor: "YouTube clips, talking-head videos, video essays, podcast video",
    howItWorks: "Keeps speaker A-roll video, makes punchy cuts & adds floating HUD graphics",
    thumbnail: (
      <svg viewBox="0 0 320 180" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="mixed-bg" x1="0" y1="0" x2="320" y2="180" gradientUnits="userSpaceOnUse">
            <stop stopColor="#090d16" />
            <stop offset="1" stopColor="#111827" />
          </linearGradient>
        </defs>
        <rect width="320" height="180" fill="url(#mixed-bg)" />
        
        {/* Left Side: A-Roll Video Footage frame */}
        <g transform="translate(18, 22)">
          <rect width="138" height="136" rx="8" fill="#1e293b" stroke="#3b82f6" strokeWidth="1.5" />
          {/* Mockup speaker face silhouette */}
          <circle cx="69" cy="55" r="24" fill="#334155" />
          <path d="M35 118c0-20 16-34 34-34s34 14 34 34" fill="#334155" />
          {/* Camera recording indicator */}
          <rect x="8" y="8" width="52" height="18" rx="4" fill="#0f172a" fillOpacity="0.8" />
          <circle cx="16" cy="17" r="3.5" fill="#ef4444" />
          <text x="26" y="21" fill="#f8fafc" fontSize="8" fontWeight="700">A-ROLL</text>
          {/* Audio Waveform */}
          <path d="M25 126v-6M35 129v-12M45 131v-16M55 128v-10M65 132v-18M75 128v-10M85 130v-14M95 127v-8M105 129v-12" stroke="#60a5fa" strokeWidth="2.5" strokeLinecap="round" />
        </g>
        
        {/* Cut / Transition divider */}
        <path d="M165 25 L160 155" stroke="#f59e0b" strokeWidth="2" strokeDasharray="4 4" opacity="0.6" />
        
        {/* Right Side: Dynamic Overlays HUD */}
        <g transform="translate(174, 22)">
          {/* Stat Overlay Card */}
          <rect width="128" height="62" rx="8" fill="#1e293b" stroke="#10b981" strokeWidth="1.5" />
          <rect x="10" y="10" width="36" height="14" rx="4" fill="#065f46" />
          <text x="28" y="20" fill="#34d399" fontSize="8" fontWeight="700" textAnchor="middle">+142%</text>
          <text x="10" y="42" fill="#f8fafc" fontSize="13" fontWeight="800">RETENTION</text>
          <path d="M80 48 L94 36 L106 42 L118 26" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          
          {/* Kinetic Callout Banner */}
          <g transform="translate(0, 72)">
            <rect width="128" height="64" rx="8" fill="#1e293b" stroke="#f59e0b" strokeWidth="1.5" />
            <rect x="10" y="10" width="108" height="16" rx="4" fill="#f59e0b" />
            <text x="64" y="22" fill="#0f172a" fontSize="9" fontWeight="800" textAnchor="middle">KEY MOMENT CUT</text>
            <rect x="10" y="34" width="70" height="8" rx="2" fill="#475569" />
            <rect x="10" y="46" width="95" height="8" rx="2" fill="#334155" />
          </g>
        </g>
      </svg>
    ),
  },
  {
    value: "explainer",
    titleKey: "tf.style.explainer",
    aboutKey: "tf.style.explainer.about",
    badge: "Motion Graphics",
    idealFor: "Business presentations, finance breakdowns, tech explainers",
    howItWorks: "Kinetic titles, stat cards, clean animated charts & modern iconography",
    thumbnail: (
      <svg viewBox="0 0 320 180" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="exp-bg" x1="0" y1="0" x2="320" y2="180" gradientUnits="userSpaceOnUse">
            <stop stopColor="#0b132b" />
            <stop offset="1" stopColor="#1c2541" />
          </linearGradient>
        </defs>
        <rect width="320" height="180" fill="url(#exp-bg)" />
        
        {/* Modern kinetic title pill */}
        <rect x="28" y="24" width="140" height="26" rx="6" fill="#3b82f6" fillOpacity="0.2" stroke="#3b82f6" strokeWidth="1" />
        <circle cx="42" cy="37" r="4" fill="#3b82f6" />
        <text x="54" y="41" fill="#93c5fd" fontSize="10" fontWeight="700" letterSpacing="0.5">MARKET ANALYSIS</text>
        
        {/* Main Glassmorphic Metric Card */}
        <g transform="translate(28, 62)">
          <rect width="150" height="92" rx="10" fill="#1e293b" fillOpacity="0.8" stroke="#334155" strokeWidth="1" />
          <text x="16" y="28" fill="#94a3b8" fontSize="10" fontWeight="600">Total Valuation</text>
          <text x="16" y="56" fill="#f8fafc" fontSize="22" fontWeight="800">$48.5M</text>
          <path d="M16 74h118" stroke="#334155" strokeWidth="1" />
          <text x="16" y="85" fill="#10b981" fontSize="9" fontWeight="700">▲ +34.2% this quarter</text>
        </g>
        
        {/* Right Data Chart */}
        <g transform="translate(192, 42)">
          <rect width="100" height="112" rx="10" fill="#0f172a" fillOpacity="0.9" stroke="#38bdf8" strokeWidth="1.5" />
          {/* Bar Chart Columns */}
          <rect x="16" y="66" width="14" height="34" rx="3" fill="#38bdf8" fillOpacity="0.4" />
          <rect x="36" y="46" width="14" height="54" rx="3" fill="#38bdf8" fillOpacity="0.6" />
          <rect x="56" y="28" width="14" height="72" rx="3" fill="#38bdf8" />
          <rect x="76" y="16" width="14" height="84" rx="3" fill="#818cf8" />
          {/* Trendline */}
          <path d="M23 60 L43 40 L63 24 L83 12" stroke="#f43f5e" strokeWidth="2.5" strokeLinecap="round" />
        </g>
      </svg>
    ),
  },
  {
    value: "stick",
    titleKey: "tf.style.stick",
    aboutKey: "tf.style.stick.about",
    badge: "Kinematic Figures",
    idealFor: "Engaging stories, humor, allegories, relatable scenarios",
    howItWorks: "15-joint kinematic characters act out dialog, gesture, point & hold signs",
    thumbnail: (
      <svg viewBox="0 0 320 180" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="stick-bg" x1="0" y1="0" x2="320" y2="180" gradientUnits="userSpaceOnUse">
            <stop stopColor="#fdfbf7" />
            <stop offset="1" stopColor="#f4ede4" />
          </linearGradient>
        </defs>
        <rect width="320" height="180" fill="url(#stick-bg)" />
        
        {/* Floor Line */}
        <line x1="20" y1="145" x2="300" y2="145" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" />
        
        {/* Character 1 (Left - Talking / Explaining with joints) */}
        <g transform="translate(68, 62)">
          {/* Head & Expression */}
          <circle cx="20" cy="18" r="14" fill="#ffffff" stroke="#1f2937" strokeWidth="3" />
          <circle cx="16" cy="16" r="2" fill="#1f2937" />
          <circle cx="24" cy="16" r="2" fill="#1f2937" />
          <path d="M17 24 Q20 27 23 24" stroke="#1f2937" strokeWidth="2" fill="none" />
          {/* Torso */}
          <line x1="20" y1="32" x2="20" y2="58" stroke="#3b82f6" strokeWidth="4" strokeLinecap="round" />
          {/* Left Arm waving */}
          <path d="M20 38 L4 28 L-4 14" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          {/* Right Arm pointing to board */}
          <path d="M20 38 L36 42 L54 36" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          {/* Kinematic IK joint dots */}
          <circle cx="4" cy="28" r="2.5" fill="#3b82f6" />
          <circle cx="36" cy="42" r="2.5" fill="#3b82f6" />
          {/* Legs */}
          <path d="M20 58 L10 72 L8 83" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M20 58 L28 72 L32 83" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        
        {/* Center Presentation Whiteboard */}
        <g transform="translate(150, 36)">
          <rect width="84" height="60" rx="6" fill="#ffffff" stroke="#1f2937" strokeWidth="3" />
          <line x1="16" y1="60" x2="10" y2="109" stroke="#1f2937" strokeWidth="3" />
          <line x1="68" y1="60" x2="74" y2="109" stroke="#1f2937" strokeWidth="3" />
          {/* Idea bulb inside whiteboard */}
          <circle cx="42" cy="26" r="10" fill="#fef08a" stroke="#ca8a04" strokeWidth="2" />
          <path d="M38 36h8M39 39h6" stroke="#ca8a04" strokeWidth="2" />
          <path d="M20 48h44" stroke="#e5e7eb" strokeWidth="3" strokeLinecap="round" />
        </g>
        
        {/* Character 2 (Right - Cheering) */}
        <g transform="translate(252, 60)">
          <circle cx="20" cy="18" r="14" fill="#ffffff" stroke="#1f2937" strokeWidth="3" />
          <circle cx="16" cy="16" r="2" fill="#1f2937" />
          <circle cx="24" cy="16" r="2" fill="#1f2937" />
          <path d="M16 23 Q20 28 24 23" stroke="#1f2937" strokeWidth="2" fill="none" />
          {/* Torso */}
          <line x1="20" y1="32" x2="20" y2="60" stroke="#ef4444" strokeWidth="4" strokeLinecap="round" />
          {/* Cheering Arms Up */}
          <path d="M20 38 L8 24 L-2 8" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" />
          <path d="M20 38 L32 24 L42 8" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" />
          {/* Legs jumping */}
          <path d="M20 60 L12 74 L8 85" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" />
          <path d="M20 60 L28 74 L32 85" stroke="#1f2937" strokeWidth="3" strokeLinecap="round" />
        </g>
        
        {/* Floating Speech / Thought Bubble */}
        <g transform="translate(30, 20)">
          <rect width="66" height="24" rx="8" fill="#ffffff" stroke="#1f2937" strokeWidth="2" />
          <text x="33" y="16" fill="#1f2937" fontSize="10" fontWeight="700" textAnchor="middle">IDEA! 💡</text>
          <path d="M50 24 L56 30 L54 24 Z" fill="#ffffff" stroke="#1f2937" strokeWidth="2" />
        </g>
      </svg>
    ),
  },
  {
    value: "cartoon",
    titleKey: "tf.style.cartoon",
    aboutKey: "tf.style.cartoon.about",
    badge: "Illustrated World",
    idealFor: "Character storybooks, moral lessons, kids & family content",
    howItWorks: "Full-color illustrated characters (Bill, Jane, etc.) in scenic backdrops",
    thumbnail: (
      <svg viewBox="0 0 320 180" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="cart-sky" x1="0" y1="0" x2="0" y2="180" gradientUnits="userSpaceOnUse">
            <stop stopColor="#bae6fd" />
            <stop offset="0.6" stopColor="#e0f2fe" />
            <stop offset="1" stopColor="#86efac" />
          </linearGradient>
        </defs>
        <rect width="320" height="180" fill="url(#cart-sky)" />
        
        {/* Background Hills */}
        <path d="M-20 180 Q60 110 160 150 T340 130 L340 180 Z" fill="#4ade80" />
        <path d="M40 180 Q160 130 260 160 T340 150 L340 180 Z" fill="#22c55e" />
        
        {/* Sun & Cloud */}
        <circle cx="280" cy="40" r="22" fill="#fde047" />
        <g fill="#ffffff" fillOpacity="0.9">
          <ellipse cx="60" cy="38" rx="22" ry="14" />
          <ellipse cx="78" cy="34" rx="16" ry="12" />
          <ellipse cx="45" cy="42" rx="14" ry="10" />
        </g>
        
        {/* Cartoon Character 1 (Bill) */}
        <g transform="translate(80, 68)">
          {/* Hair */}
          <path d="M18 10 Q28 0 42 12 Q48 18 46 26 L14 26 Z" fill="#92400e" />
          {/* Face */}
          <circle cx="30" cy="26" r="15" fill="#fde047" />
          <circle cx="26" cy="24" r="2.5" fill="#1e293b" />
          <circle cx="34" cy="24" r="2.5" fill="#1e293b" />
          <path d="M26 31 Q30 36 34 31" stroke="#1e293b" strokeWidth="2" strokeLinecap="round" fill="none" />
          {/* Shirt */}
          <path d="M16 41 Q30 38 44 41 L46 72 Q30 75 14 72 Z" fill="#3b82f6" />
          {/* Collar */}
          <polygon points="30,48 24,40 36,40" fill="#ffffff" />
          {/* Legs */}
          <rect x="18" y="72" width="10" height="26" rx="4" fill="#1e293b" />
          <rect x="32" y="72" width="10" height="26" rx="4" fill="#1e293b" />
        </g>
        
        {/* Cartoon Character 2 (Jane) */}
        <g transform="translate(175, 64)">
          {/* Ponytail Hair */}
          <circle cx="50" cy="22" r="10" fill="#d97706" />
          <circle cx="30" cy="28" r="15" fill="#fed7aa" />
          <path d="M16 26 Q28 12 44 26" fill="#d97706" />
          <circle cx="26" cy="26" r="2.5" fill="#1e293b" />
          <circle cx="34" cy="26" r="2.5" fill="#1e293b" />
          <path d="M26 33 Q30 38 34 33" stroke="#e11d48" strokeWidth="2" strokeLinecap="round" fill="none" />
          {/* Dress */}
          <path d="M22 43 L10 74 L50 74 L38 43 Z" fill="#ec4899" />
          {/* Legs */}
          <rect x="20" y="74" width="8" height="26" rx="3" fill="#fed7aa" />
          <rect x="32" y="74" width="8" height="26" rx="3" fill="#fed7aa" />
        </g>
      </svg>
    ),
  },
  {
    value: "emoji",
    titleKey: "tf.style.emoji",
    aboutKey: "tf.style.emoji.about",
    badge: "Pop & Reactions",
    idealFor: "TikTok, Reels, Shorts, high-energy hooks & punchlines",
    howItWorks: "Large 3D expressive emojis that react to every key sentence and sentiment",
    thumbnail: (
      <svg viewBox="0 0 320 180" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="em-bg" x1="0" y1="0" x2="320" y2="180" gradientUnits="userSpaceOnUse">
            <stop stopColor="#3b0764" />
            <stop offset="0.5" stopColor="#1e1b4b" />
            <stop offset="1" stopColor="#0f172a" />
          </linearGradient>
        </defs>
        <rect width="320" height="180" fill="url(#em-bg)" />
        
        {/* Floating Reaction Wave Particle Trails */}
        <path d="M20 120 Q80 80 160 120 T300 100" stroke="#f43f5e" strokeWidth="2" strokeDasharray="6 6" opacity="0.4" />
        <path d="M20 70 Q90 110 170 70 T300 90" stroke="#38bdf8" strokeWidth="2" strokeDasharray="6 6" opacity="0.4" />
        
        {/* Central Hero Emoji (Star Struck) */}
        <g transform="translate(125, 45)">
          <circle cx="35" cy="35" r="34" fill="#fbbf24" stroke="#f59e0b" strokeWidth="3" />
          {/* Star Eyes */}
          <path d="M22 22 L24 28 L30 29 L25 33 L27 39 L22 35 L17 39 L19 33 L14 29 L20 28 Z" fill="#ec4899" />
          <path d="M48 22 L50 28 L56 29 L51 33 L53 39 L48 35 L43 39 L45 33 L40 29 L46 28 Z" fill="#ec4899" />
          {/* Wide Open Smile */}
          <path d="M20 44 Q35 62 50 44 Z" fill="#831843" />
          <path d="M28 52 Q35 56 42 52 Z" fill="#f43f5e" />
        </g>
        
        {/* Left Floating Emoji (Fire 🔥) */}
        <g transform="translate(36, 55)">
          <circle cx="25" cy="25" r="22" fill="#1e1b4b" fillOpacity="0.8" stroke="#f97316" strokeWidth="1.5" />
          <text x="25" y="32" fontSize="22" textAnchor="middle">🔥</text>
        </g>
        
        {/* Right Floating Emoji (Rocket 🚀) */}
        <g transform="translate(235, 55)">
          <circle cx="25" cy="25" r="22" fill="#1e1b4b" fillOpacity="0.8" stroke="#a855f7" strokeWidth="1.5" />
          <text x="25" y="32" fontSize="22" textAnchor="middle">🚀</text>
        </g>
        
        {/* Bottom Reaction Pill */}
        <rect x="70" y="140" width="180" height="24" rx="12" fill="#0f172a" fillOpacity="0.9" stroke="#fbbf24" strokeWidth="1.5" />
        <text x="160" y="156" fill="#f8fafc" fontSize="11" fontWeight="800" textAnchor="middle">EXPRESSIVE POP SYNC</text>
      </svg>
    ),
  },
];
