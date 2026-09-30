import { useEffect, useState } from "react";
import OrbitMark from "./OrbitMark";

// Mounted above routing so direct /chat and /demo loads also get the entrance.
export default function StartupIntro() {
  const [visible, setVisible] = useState(
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(false), 2200);
    return () => window.clearTimeout(timer);
  }, []);
  if (!visible) return null;
  return (
    <div className="orbit-startup-intro" aria-hidden="true">
      <OrbitMark state="landing" />
    </div>
  );
}
