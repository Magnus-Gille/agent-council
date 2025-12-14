import { useEffect, useState } from 'react';

interface Snowflake {
  id: number;
  x: number;
  size: number;
  animationDuration: number;
  opacity: number;
  delay: number;
}

export function ChristmasEffects() {
  const [snowflakes, setSnowflakes] = useState<Snowflake[]>([]);

  useEffect(() => {
    const flakes: Snowflake[] = [];
    for (let i = 0; i < 60; i++) {
      flakes.push({
        id: i,
        x: Math.random() * 100,
        size: Math.random() * 10 + 6,
        animationDuration: Math.random() * 8 + 6,
        opacity: Math.random() * 0.7 + 0.3,
        delay: Math.random() * 8,
      });
    }
    setSnowflakes(flakes);
  }, []);

  // Generate Christmas lights colors
  const lightColors = ['#ff0000', '#00ff00', '#FFD700', '#0000ff', '#ff00ff'];

  return (
    <>
      {/* Snowflakes */}
      <div className="snowflakes-container">
        {snowflakes.map((flake) => (
          <div
            key={flake.id}
            className="snowflake"
            style={{
              left: `${flake.x}%`,
              fontSize: `${flake.size}px`,
              animationDuration: `${flake.animationDuration}s`,
              opacity: flake.opacity,
              animationDelay: `${flake.delay}s`,
            }}
          >
            ❄
          </div>
        ))}
      </div>

      {/* Christmas Lights at top */}
      <div className="christmas-lights">
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className="light-bulb"
            style={{
              backgroundColor: lightColors[i % lightColors.length],
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </div>

      {/* Christmas Tree */}
      <div className="christmas-tree">
        <div className="tree-star">⭐</div>
        <div className="tree-top">🎄</div>
        <div className="tree-gifts">🎁🎀🎁</div>
      </div>

      {/* Corner decorations */}
      <div className="corner-decoration top-left">🔔</div>
      <div className="corner-decoration top-right">🔔</div>

      {/* Holly decoration */}
      <div className="holly-left">🍀</div>
      <div className="holly-right">🍀</div>

      {/* Candy canes */}
      <div className="candy-cane-left">🍬</div>
      <div className="candy-cane-right">🍬</div>
    </>
  );
}
