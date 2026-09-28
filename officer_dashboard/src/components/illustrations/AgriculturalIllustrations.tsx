import React from 'react';

/**
 * Universal Farmer Product Design System — Agricultural & Weather SVG Illustrations
 * Zero external image dependencies — lightweight, scalable, and crisp on all displays.
 */

interface IllustrationProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Clean stylized vector illustration of green furrowed agricultural fields,
 * warm morning sun, and a sprouting crop seedling.
 */
export const AgriFieldIllustration: React.FC<IllustrationProps> = ({ size = 120, className = '', style }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={style}
      aria-hidden="true"
    >
      {/* Background Soft Circle */}
      <circle cx="60" cy="60" r="54" fill="var(--primary-050, #EFFAF4)" stroke="var(--primary-100, #DDF3E8)" strokeWidth="1.5" />

      {/* Gentle Morning Sun */}
      <circle cx="60" cy="42" r="16" fill="var(--sun-100, #FEF9E7)" />
      <circle cx="60" cy="42" r="11" fill="var(--sun-500, #F6C744)" />

      {/* Background Hill */}
      <path
        d="M12 78C32 68 55 74 72 70C88 66 102 73 108 78L108 104L12 104Z"
        fill="var(--primary-500, #0A8A57)"
        opacity="0.85"
      />

      {/* Foreground Rolling Field Furrows */}
      <path
        d="M10 88C35 78 68 84 110 88L110 108L10 108Z"
        fill="var(--primary-700, #056B43)"
      />

      {/* Furrow Accent Lines */}
      <path d="M26 92L38 104" stroke="rgba(221, 243, 232, 0.45)" strokeWidth="1.75" strokeLinecap="round" />
      <path d="M50 90L62 104" stroke="rgba(221, 243, 232, 0.45)" strokeWidth="1.75" strokeLinecap="round" />
      <path d="M74 92L86 104" stroke="rgba(221, 243, 232, 0.45)" strokeWidth="1.75" strokeLinecap="round" />

      {/* Sprouting Young Seedling */}
      <path
        d="M60 74C60 67 64 64 68 64C68 68 65 72 60 74Z"
        fill="var(--surface, #FFFFFF)"
      />
      <path
        d="M60 74C60 68 56 65 52 65C52 69 55 72 60 74Z"
        fill="var(--surface, #FFFFFF)"
      />
      <circle cx="60" cy="74" r="2" fill="var(--primary-100, #DDF3E8)" />
    </svg>
  );
};

/**
 * Stylized Topography cross-section showing Mountain Ridge (High Orographic Rain)
 * vs Valley / Plains (Moderate/Low Rain), visually explaining downscaling.
 */
export const TopographyDownscalingIllustration: React.FC<{
  width?: number;
  height?: number;
  className?: string;
  style?: React.CSSProperties;
}> = ({
  width = 280,
  height = 90,
  className = '',
  style,
}) => {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 280 90"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={style}
      aria-hidden="true"
    >
      {/* Background Frame */}
      <rect width="280" height="90" rx="14" fill="var(--surface-subtle, #F8F9F7)" />

      {/* High Elevation Ridge (Left) */}
      <path
        d="M20 78L78 30L135 78H20Z"
        fill="var(--ink-700, #425149)"
      />
      {/* Ridge Peak Accent */}
      <path
        d="M78 30L70 42H86L78 30Z"
        fill="rgba(255, 255, 255, 0.6)"
      />

      {/* Valley Agricultural Floor (Right) */}
      <path
        d="M115 78C155 64 195 72 260 78V82H115V78Z"
        fill="var(--primary-600, #087A4B)"
      />

      {/* Orographic Cloud over Ridge */}
      <circle cx="78" cy="22" r="12" fill="var(--info-600, #3D78A6)" />
      <circle cx="66" cy="24" r="9" fill="var(--info-600, #3D78A6)" />
      <circle cx="90" cy="24" r="9" fill="var(--info-600, #3D78A6)" />

      {/* Rain Streaks over Ridge */}
      <line x1="68" y1="38" x2="64" y2="48" stroke="var(--info-600, #3D78A6)" strokeWidth="1.75" strokeLinecap="round" />
      <line x1="78" y1="38" x2="74" y2="49" stroke="var(--info-600, #3D78A6)" strokeWidth="1.75" strokeLinecap="round" />
      <line x1="88" y1="38" x2="84" y2="48" stroke="var(--info-600, #3D78A6)" strokeWidth="1.75" strokeLinecap="round" />

      {/* Gentle Sun over Valley (Right) */}
      <circle cx="215" cy="36" r="11" fill="var(--sun-100, #FEF9E7)" />
      <circle cx="215" cy="36" r="7" fill="var(--sun-500, #F6C744)" />

      {/* Labels */}
      <text x="78" y="72" textAnchor="middle" fill="#FFFFFF" fontSize="8.5" fontWeight="700">Ridge (High Rain)</text>
      <text x="195" y="80" textAnchor="middle" fill="#FFFFFF" fontSize="8.5" fontWeight="700">Valley / Plains</text>
    </svg>
  );
};

/**
 * Weather state vector visual matching IMD rainfall categorization.
 */
interface WeatherStateProps {
  rainfallMm: number;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

export const WeatherStateIllustration: React.FC<WeatherStateProps> = ({
  rainfallMm,
  size = 52,
  className = '',
  style,
}) => {
  const isHeavy = rainfallMm >= 64.5;
  const isModerate = rainfallMm >= 7.6 && rainfallMm < 64.5;
  const isLight = rainfallMm > 0 && rainfallMm < 7.6;
  const isClear = rainfallMm === 0;

  const bgColor = isHeavy
    ? 'var(--danger-100, #FDE8E6)'
    : isModerate
    ? 'var(--primary-050, #EFFAF4)'
    : isLight
    ? 'var(--info-100, #E3F2FD)'
    : 'var(--sun-100, #FEF9E7)';

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 52 52"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={style}
      aria-hidden="true"
    >
      <rect width="52" height="52" rx="14" fill={bgColor} />

      {isClear && (
        <>
          <circle cx="26" cy="26" r="14" fill="var(--sun-500, #F6C744)" opacity="0.25" />
          <circle cx="26" cy="26" r="9" fill="var(--sun-500, #F6C744)" />
          {/* Subtle Sun Rays */}
          <line x1="26" y1="9" x2="26" y2="13" stroke="var(--sun-500, #F6C744)" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="26" y1="39" x2="26" y2="43" stroke="var(--sun-500, #F6C744)" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="9" y1="26" x2="13" y2="26" stroke="var(--sun-500, #F6C744)" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="39" y1="26" x2="43" y2="26" stroke="var(--sun-500, #F6C744)" strokeWidth="1.5" strokeLinecap="round" />
        </>
      )}

      {!isClear && (
        <>
          {/* Cloud Body */}
          <circle
            cx="22"
            cy="23"
            r="8"
            fill={isHeavy ? '#6B7280' : isModerate ? 'var(--primary-600, #087A4B)' : 'var(--info-600, #3D78A6)'}
          />
          <circle
            cx="31"
            cy="24"
            r="6.5"
            fill={isHeavy ? '#6B7280' : isModerate ? 'var(--primary-600, #087A4B)' : 'var(--info-600, #3D78A6)'}
          />
          <circle
            cx="16"
            cy="25"
            r="5"
            fill={isHeavy ? '#6B7280' : isModerate ? 'var(--primary-600, #087A4B)' : 'var(--info-600, #3D78A6)'}
          />
          <rect
            x="14"
            y="25"
            width="20"
            height="6"
            rx="3"
            fill={isHeavy ? '#6B7280' : isModerate ? 'var(--primary-600, #087A4B)' : 'var(--info-600, #3D78A6)'}
          />

          {/* Rain / Lightning Accents */}
          {isHeavy ? (
            <>
              {/* Lightning Bolt */}
              <path
                d="M27 31L23 37H26L24 43L30 35H27L27 31Z"
                fill="var(--warning-600, #C78318)"
              />
              <line x1="17" y1="34" x2="15" y2="40" stroke="var(--danger-600, #C94B43)" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="35" y1="34" x2="33" y2="40" stroke="var(--danger-600, #C94B43)" strokeWidth="1.5" strokeLinecap="round" />
            </>
          ) : (
            <>
              <line
                x1="18"
                y1="34"
                x2="16"
                y2="40"
                stroke={isModerate ? 'var(--primary-600, #087A4B)' : 'var(--info-600, #3D78A6)'}
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <line
                x1="25"
                y1="34"
                x2="23"
                y2="40"
                stroke={isModerate ? 'var(--primary-600, #087A4B)' : 'var(--info-600, #3D78A6)'}
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              {isModerate && (
                <line
                  x1="32"
                  y1="34"
                  x2="30"
                  y2="40"
                  stroke="var(--primary-600, #087A4B)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              )}
            </>
          )}
        </>
      )}
    </svg>
  );
};
