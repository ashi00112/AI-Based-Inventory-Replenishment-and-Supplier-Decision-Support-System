import React, { useState, useEffect, useRef } from 'react';

const BRAND_NAME = 'SmartSupply AI';

/**
 * AnimatedBrand Component:
 * - Logo performs one smooth 360-degree rotation on mount and every 10 seconds.
 * - Brand text reveals horizontally letter-by-letter on one line without layout shifts.
 * - Both animations synchronously repeat every 10 seconds (1s active, ~9s static).
 * - Respects prefers-reduced-motion.
 * - Cleans all intervals/timeouts on unmount.
 */
const CYCLE_INTERVAL_MS = 10000; // 10 seconds cycle
const ROTATION_DURATION_MS = 1050; // ~1 second rotation
const REVEAL_DURATION_MS = 950; // ~1 second text reveal

export default function AnimatedBrand({
  subtitle = 'Inventory Intelligence',
  showSubtitle = true,
  size = 'md', // 'sm' | 'md' | 'lg'
  className = '',
}) {
  const [displayedText, setDisplayedText] = useState(BRAND_NAME);
  const [isRotating, setIsRotating] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  const timersRef = useRef([]);

  const clearAllTimers = () => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
  };

  useEffect(() => {
    // Detect reduced motion preference
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);

    const handleMotionChange = (e) => {
      setPrefersReducedMotion(e.matches);
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleMotionChange);
    }

    if (mediaQuery.matches) {
      setDisplayedText(BRAND_NAME);
      return () => {
        if (mediaQuery.removeEventListener) {
          mediaQuery.removeEventListener('change', handleMotionChange);
        }
      };
    }

    // Function to run synchronized logo rotation + typewriter animation
    const triggerSynchronizedAnimation = () => {
      clearAllTimers();

      // Trigger 1-second 360-degree rotation
      setIsRotating(true);
      const rotTimer = setTimeout(() => {
        setIsRotating(false);
      }, ROTATION_DURATION_MS);
      timersRef.current.push(rotTimer);

      // Letter-by-letter horizontal typewriter reveal
      setDisplayedText('');
      const fullLength = BRAND_NAME.length;
      const stepDuration = Math.max(35, Math.floor(REVEAL_DURATION_MS / fullLength));

      for (let i = 1; i <= fullLength; i++) {
        const typeTimer = setTimeout(() => {
          setDisplayedText(BRAND_NAME.slice(0, i));
        }, i * stepDuration);
        timersRef.current.push(typeTimer);
      }
    };

    // Run once on load
    triggerSynchronizedAnimation();

    // Repeat synchronized cycle every 10 seconds
    const intervalId = setInterval(() => {
      triggerSynchronizedAnimation();
    }, CYCLE_INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
      clearAllTimers();
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handleMotionChange);
      }
    };
  }, []);

  // Size styling variants
  const logoSizes = {
    sm: 'w-7 h-7 text-xs',
    md: 'w-9 h-9 text-sm',
    lg: 'w-12 h-12 text-base',
  };

  const titleSizes = {
    sm: 'text-sm font-bold',
    md: 'text-base font-bold',
    lg: 'text-2xl sm:text-3xl font-black',
  };

  const subtitleSizes = {
    sm: 'text-[9px]',
    md: 'text-[10px]',
    lg: 'text-xs',
  };

  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      {/* Brand Logo with 360-degree rotation animation */}
      <div
        className={`relative shrink-0 ${logoSizes[size]} rounded-xl flex items-center justify-center shadow-lg transition-transform ${
          isRotating && !prefersReducedMotion ? 'animate-spin-once' : ''
        }`}
        style={{
          background: 'linear-gradient(135deg, #014651 0%, #025866 50%, #03D26F 100%)',
          boxShadow: '0 4px 14px rgba(3, 210, 111, 0.25)',
        }}
        aria-hidden="true"
      >
        {/* Subtle inner geometric icon */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="w-5 h-5 text-white"
        >
          {/* Isometric supply node cube with AI intelligence core */}
          <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
          <path d="m3.3 7 8.7 5 8.7-5" stroke="#CEF431" />
          <path d="M12 22V12" stroke="#03D26F" />
        </svg>

        {/* Small accent beacon */}
        <span
          className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full border border-cyprus-900"
          style={{ backgroundColor: '#CEF431' }}
        />
      </div>

      {/* Brand Text Block — Strict Single-Line Horizontal Reveal */}
      <div className="flex flex-col justify-center min-w-0">
        <div className="flex items-center whitespace-nowrap overflow-hidden">
          <span
            className={`${titleSizes[size]} tracking-tight text-white leading-tight font-sans inline-block whitespace-nowrap`}
          >
            {prefersReducedMotion ? BRAND_NAME : displayedText || '\u00A0'}
          </span>
          {/* Soft AI accent badge */}
          <span
            className="ml-1.5 px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider uppercase border border-malachite/30"
            style={{
              backgroundColor: 'rgba(3, 210, 111, 0.12)',
              color: '#03D26F',
            }}
          >
            AI
          </span>
        </div>

        {showSubtitle && (
          <span
            className={`${subtitleSizes[size]} text-cyprus-200/70 block leading-tight font-medium tracking-wide mt-0.5 truncate`}
          >
            {subtitle}
          </span>
        )}
      </div>
    </div>
  );
}
