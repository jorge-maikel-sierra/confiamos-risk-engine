import Link from "next/link";
import { ShieldCheck, PlusCircle, Inbox } from "lucide-react";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-600 rounded-lg text-white">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <Link href="/underwritings" className="font-bold text-lg text-slate-900 tracking-tight hover:text-blue-600 transition">
              Confiamos Risk Engine
            </Link>
            <span className="block text-xs text-slate-500 font-medium">
              Cooperativa Financiera Confiamos
            </span>
          </div>
        </div>

        <nav className="flex items-center space-x-4">
          <Link
            href="/underwritings"
            className="flex items-center space-x-1.5 px-3 py-2 rounded-md text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 transition"
          >
            <Inbox className="w-4 h-4" />
            <span>Bandeja de Créditos</span>
          </Link>
          <Link
            href="/underwritings/new"
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Nueva Solicitud</span>
          </Link>
        </nav>
      </div>
    </header>
  );
}
