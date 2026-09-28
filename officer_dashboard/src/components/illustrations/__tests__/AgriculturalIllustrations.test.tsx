import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import {
  AgriFieldIllustration,
  TopographyDownscalingIllustration,
  WeatherStateIllustration,
} from '../AgriculturalIllustrations';

describe('Phase 4.6 React Agricultural Illustrations Tests', () => {
  it('renders AgriFieldIllustration with correct SVG geometry and styling', () => {
    const { container } = render(<AgriFieldIllustration size={120} className="test-class" />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('width', '120');
    expect(svg).toHaveAttribute('height', '120');
    expect(svg).toHaveClass('test-class');
    expect(svg?.querySelectorAll('circle').length).toBeGreaterThan(0);
    expect(svg?.querySelectorAll('path').length).toBeGreaterThan(0);
  });

  it('renders TopographyDownscalingIllustration with ridge and valley labels', () => {
    const { container, getByText } = render(<TopographyDownscalingIllustration width={300} height={160} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('width', '300');
    expect(svg).toHaveAttribute('height', '160');
    expect(getByText('Ridge (High Rain)')).toBeInTheDocument();
    expect(getByText('Valley / Plains')).toBeInTheDocument();
  });

  it('renders WeatherStateIllustration for clear, light rain, moderate rain, and heavy rain states', () => {
    // 1. Clear weather
    const { container, rerender } = render(<WeatherStateIllustration rainfallMm={0} size={48} />);
    let svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('width', '48');

    // 2. Light rain
    rerender(<WeatherStateIllustration rainfallMm={4.2} size={48} />);
    svg = container.querySelector('svg');
    expect(svg?.querySelectorAll('line').length).toBeGreaterThan(0);

    // 3. Moderate rain
    rerender(<WeatherStateIllustration rainfallMm={25.0} size={48} />);
    svg = container.querySelector('svg');
    expect(svg?.querySelectorAll('line').length).toBeGreaterThan(0);

    // 4. Heavy rain
    rerender(<WeatherStateIllustration rainfallMm={80.0} size={48} />);
    svg = container.querySelector('svg');
    expect(svg?.querySelectorAll('path').length).toBeGreaterThan(0);
  });
});
