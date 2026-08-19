import { Waves } from "lucide-react";
import logo from "../assets/WELL-LABS_Coloured-logo.png";

export default function NavBar() {
  return (
    <header className="sticky top-0 z-40 border-b border-canal-100 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <img
            src={logo}
            alt="Canal Blockage Detection Logo"
            className="w-auto h-10"
          />
        </div>

        <nav className="hidden items-center gap-8 md:flex">
          <a href="#upload" className="text-sm font-medium text-canal-800 transition hover:text-teal-500">
            Run Analysis
          </a>
          <a href="#how-it-works" className="text-sm font-medium text-canal-800 transition hover:text-teal-500">
            How It Works
          </a>
          <a
            href="#upload"
            className="rounded-md bg-canal-800 px-4 py-2 text-sm font-medium text-white transition hover:bg-canal-700"
          >
            New Survey Scan
          </a>
        </nav>
      </div>
    </header>
  );
}
