import { Waves } from "lucide-react";
import logo from "../assets/Full-logo_White.png"
export default function Footer() {
  return (
    <footer className="border-t border-canal-100 bg-canal-950 text-canal-100/70">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 sm:flex-row">
        <div className="flex items-center gap-3">
          <img
            src={logo}
            alt="Canal Blockage Detection Logo"
            className="w-auto h-10"
          />
        </div>
        <p className="font-mono text-xs text-canal-100/40">
          Built for irrigation & flood-control field operations
        </p>
      </div>
    </footer>
  );
}
